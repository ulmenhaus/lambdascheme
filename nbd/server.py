#! /usr/local/bin/python3

import logging
import os
import random
import socket
import _thread
import threading
import time
import uuid

import jaeger_client

from http.server import BaseHTTPRequestHandler, HTTPServer

from nbd.iptr import NBDInterpreter, MagicValues, next_n_bytes
from pysyncobj import SyncObj, SyncObjConsumer
from pysyncobj.batteries import ReplCounter, ReplList
from pysyncobj.config import SyncObjConf
from pysyncobj.syncobj import AsyncResult, replicated

DEFAULT_BLOCK_SIZE = 512  # bytes
DEFAULT_BLOCK_COUNT = (2**20)  # 512MiB
DEFAULT_DEVICE_SIZE = DEFAULT_BLOCK_SIZE * DEFAULT_BLOCK_COUNT


def handle_cxn(cxn, blocks, volumes, tracer):
    iptr = NBDInterpreter(cxn)
    volume = None
    for opt in iptr.get_client_options():
        if opt.kind == MagicValues.OptionsExportName:
            volume = opt.data
        else:
            # we don't support any extra options
            logging.info("Ignoring client option: {}".format(opt.kind))
            iptr.send_option_unsupported(opt)

    if volume not in volumes:
        # NOTE some short-cuts here for simple implementation
        # * race condition if creating the same volume twice
        # * volumes may sync faster than blocks causing index error
        # * volume lookup is O(n) but could be O(log(n))
        if isinstance(volumes, list):
            volumes.append(volume)
            blocks.extend([b'\x00'] * DEFAULT_DEVICE_SIZE)
        else:
            volumes.append(volume, sync=True)
            volix = volumes.index(volume)
            blocks.write_zeros(volix * DEFAULT_DEVICE_SIZE,
                               DEFAULT_DEVICE_SIZE)
            # blocks.extend_zeros(DEFAULT_DEVICE_SIZE, sync=True)

    voloffset = DEFAULT_DEVICE_SIZE * volumes.index(volume)
    iptr.send_export_response(DEFAULT_DEVICE_SIZE)
    logging.info("Entering transmission phase")
    for req in iptr.get_transmission_requests():
        if req.kind == MagicValues.RequestKindRead:
            logging.info("Reading bytes {} - {} of {}".format(
                req.offset, req.offset + req.length, volume.decode("utf-8")))
            start = voloffset + req.offset
            data = blocks.read(req.offset, req.length)
            # data = b"".join(blocks[start:start + req.length])
            iptr.send_transmission_response(req.handle, data)
        elif req.kind == MagicValues.RequestKindWrite:
            logging.info("Writing bytes {} - {} of {}".format(
                req.offset, req.offset + req.length, volume.decode("utf-8")))
            start = voloffset + req.offset
            with tracer.start_span('write-all-replicas'):
                blocks.lead_write(start, req.data)
            # blocks[start:start + req.length] = [
            #     b.to_bytes(byteorder="big", length=1) for b in req.data
            # ]
            iptr.send_transmission_response(req.handle)
        elif req.kind == MagicValues.RequestKindClose:
            cxn.shutdown(socket.SHUT_RDWR)
            cxn.close
            break
        else:
            raise ValueError("Unknown request type: {}".format(req.kind))


class ReplBlocks(ReplList):
    @replicated
    def setslicesubset(self, i, j, sequence):
        self.rawData()[i:j] = sequence

    @replicated
    def extend_zeros(self, count):
        self.rawData().extend([b'\x00'] * count)

    # Break up the write, otherwise it may pickle beyond the size of one packet
    # and PySyncObj isn't set up for that
    def setslice(self, i, j, sequence):
        size = 2**12
        asyncs = []
        offset = i
        while offset < j:
            end = min(offset + size, j)
            asc = AsyncResult()
            self.setslicesubset(offset,
                                end,
                                sequence[offset - i:end - i],
                                callback=asc.onResult)
            asyncs.append(asc)
            offset += size

        for asc in asyncs:
            asc.event.wait(None)

    def __setitem__(self, k, v):
        if isinstance(k, slice):
            self.setslice(k.start, k.stop, v)
        else:
            super()[k] = v


class HealthHandler(BaseHTTPRequestHandler):
    counter = None

    def do_GET(s):
        if not HealthHandler.counter:
            s.send_response(200)
            s.end_headers()
            s.wfile.write(b"OK")
            return
        inc_value = random.choice([1, -1])
        try:
            HealthHandler.counter.add(inc_value)
            s.send_response(200)
            s.end_headers()
            s.wfile.write(b"OK")
        except:
            s.send_response(500)
            s.end_headers()
            s.wfile.write(b"Error writing to distributed log")


class LoglessCache(object):
    def __init__(self, capacity=100):
        self._roundrobin = [b''] * capacity
        self._uuid2write = {}
        self._lock = threading.Lock()
        self._ix = 0

    def set(self, newuuid, val):
        with self._lock:
            curuuid = self._roundrobin[self._ix]
            if curuuid in self._uuid2write:
                del self._uuid2write[curuuid]
            self._roundrobin[self._ix] = newuuid
            self._uuid2write[newuuid] = val
            self._ix = (self._ix + 1) % len(self._roundrobin)

    def get(self, write_uuid):
        with self._lock:
            return self._uuid2write.get(write_uuid, b'')


class WriteSharer(object):
    def __init__(self, peers, cache):
        self.peers = peers
        self.locks = {peer: threading.Lock() for peer in self.peers}
        self.cache = cache
        self.clients = {}

    def listen_for_asks(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 2002))
        sock.setblocking(True)
        sock.listen(1)
        while True:
            cxn, _client = sock.accept()
            _thread.start_new_thread(self._handle_asks, (cxn, ))

    def _handle_asks(self, cxn):
        while True:
            write_uuid_len = int.from_bytes(next_n_bytes(cxn, 4),
                                            byteorder="big")
            write_uuid = next_n_bytes(cxn, write_uuid_len)
            write = self.cache.get(write_uuid)
            cxn.sendall(len(write).to_bytes(byteorder="big", length=4))
            cxn.sendall(write)

    def get_write(self, write_uuid, check_first):
        peers = list(self.peers)
        if check_first in peers:
            peers.remove(check_first)
            peers.insert(0, check_first)
        write = self.cache.get(write_uuid)
        if write != b'':
            return write
        for peer in peers:
            with self.locks[peer]:
                client = self.clients.get(peer)
                if client is None:
                    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    client.connect((peer, 2002))
                    self.clients[peer] = client
                client.sendall(
                    len(write_uuid).to_bytes(byteorder="big", length=4))
                client.sendall(write_uuid)
                write_len = int.from_bytes(next_n_bytes(client, 4),
                                           byteorder="big")
                if write_len != 0:
                    return next_n_bytes(client, write_len)
        raise ValueError("Write not found", write_uuid)


class LocalState(object):
    f = None
    write_sharer = None
    lock = None
    hostname = None
    write_count = None


class ReplFile(SyncObjConsumer):
    @replicated
    def write(self, originator, offset, write_uuid):
        try:
            write = LocalState.write_sharer.get_write(write_uuid, originator)
            with LocalState.lock:
                logging.info("Writing {} to offset {}".format(
                    write_uuid, offset))
                LocalState.f.seek(offset)
                LocalState.f.write(write)
        except ValueError:
            logging.error(
                "Failed to write {} to offset {} -- block not found among peers"
                .format(write_uuid, offset))

    @replicated
    def write_zeros(self, offset, length):
        with LocalState.lock:
            LocalState.f.seek(offset)
            LocalState.f.write(b'\x00' * length)

    def read(self, offset, length):
        with LocalState.lock:
            LocalState.f.seek(offset)
            return LocalState.f.read(length)

    def lead_write(self, offset, data):
        sync = False
        with LocalState.lock:
            LocalState.write_count += 1
            if LocalState.write_count >= 20:
                LocalState.write_count = 0
                sync = True
        write_uuid = uuid.uuid1().bytes
        LocalState.write_sharer.cache.set(write_uuid, data)
        self.write(LocalState.hostname, offset, write_uuid, sync=sync)


def main():
    # log everything to stderr because compose containers for some reason aren't logging stdout
    logging.basicConfig(level=logging.DEBUG,
                        filename='/proc/self/fd/2',
                        filemode='w')

    peers = None if "NBDD_PEERS" not in os.environ else os.environ[
        "NBDD_PEERS"].split(",")
    hostname = os.environ.get("NBDD_HOSTNAME")
    # contains all blocks for all devices as a contiguous list of bytes
    blocks = []
    # a list of all devices so we know the starting offset of a given device in `blocks`
    # (all devices are fixed size)
    volumes = []

    tracer = jaeger_client.Config(
        config={
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name='nbd',
    ).initialize_tracer()

    if peers:
        LocalState.f = open('/tmp/blocks', 'r+b')
        write_cache = LoglessCache()
        LocalState.write_sharer = WriteSharer(peers, write_cache)
        _thread.start_new_thread(LocalState.write_sharer.listen_for_asks, ())
        LocalState.lock = threading.Lock()
        LocalState.hostname = hostname
        LocalState.write_count = 0
        blocks = ReplFile()
        volumes = ReplList()
        health_counter = ReplCounter()
        HealthHandler.counter = health_counter
        self_address = "{}:2001".format(hostname)
        peer_addresses = ["{}:2001".format(peer) for peer in peers]
        syncObj = SyncObj(self_address,
                          peer_addresses,
                          consumers=[blocks, volumes, health_counter])

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('0.0.0.0', 2000))
    sock.setblocking(True)
    sock.listen(1)

    httpd = HTTPServer(('0.0.0.0', 8080), HealthHandler)
    _thread.start_new_thread(httpd.serve_forever, ())

    # Prototype will listen to one client at a time
    # -- can be made concurrent without much extra work
    logging.info("NBD Server '{}' Starting with peers {}...".format(
        hostname, peers))
    while True:
        cxn, client = sock.accept()
        logging.info("Connection accepted from client {}".format(client))
        _thread.start_new_thread(handle_cxn, (cxn, blocks, volumes, tracer))
        logging.info(
            "Connection closed by client {} -- listening for next client".
            format(client))


if __name__ == "__main__":
    main()
