#! /usr/local/bin/python3

import logging
import os
import random
import socket
import _thread

from http.server import BaseHTTPRequestHandler, HTTPServer

from nbd.iptr import NBDInterpreter, MagicValues
from pysyncobj import SyncObj
from pysyncobj.batteries import ReplCounter, ReplList
from pysyncobj.syncobj import AsyncResult, replicated

DEFAULT_BLOCK_SIZE = 512  # bytes
DEFAULT_BLOCK_COUNT = (2**13)  # 4MiB
DEFAULT_DEVICE_SIZE = DEFAULT_BLOCK_SIZE * DEFAULT_BLOCK_COUNT


def handle_cxn(cxn, blocks, volumes):
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
        # HACK assume volumes is a SyncObj if it is not a list
        kwargs = {} if isinstance(volumes, list) else {"sync": True}
        # NOTE some short-cuts here for simple implementation
        # * race condition if creating the same volume twice
        # * volumes may sync faster than blocks causing index error
        # * volume lookup is O(n) but could be O(log(n))
        volumes.append(volume, **kwargs)
        blocks.extend([b'\x00'] * DEFAULT_DEVICE_SIZE, **kwargs)

    voloffset = DEFAULT_DEVICE_SIZE * volumes.index(volume)
    iptr.send_export_response(DEFAULT_DEVICE_SIZE)
    logging.info("Entering transmission phase")
    for req in iptr.get_transmission_requests():
        if req.kind == MagicValues.RequestKindRead:
            logging.info("Reading bytes {} - {} of {}".format(
                req.offset, req.offset + req.length, volume.decode("utf-8")))
            start = voloffset + req.offset
            data = b"".join(blocks[start:start + req.length])
            iptr.send_transmission_response(req.handle, data)
        elif req.kind == MagicValues.RequestKindWrite:
            logging.info("Writing bytes {} - {} of {}".format(
                req.offset, req.offset + req.length, volume.decode("utf-8")))
            start = voloffset + req.offset
            blocks[start:start + req.length] = [
                b.to_bytes(byteorder="big", length=1) for b in req.data
            ]
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


def main():
    # log everything to stderr because compose containers for some reason aren't logging stdout
    logging.basicConfig(level=logging.DEBUG,
                        filename='/proc/self/fd/2',
                        filemode='w')

    peers = None if "NBDD_PEERS" not in os.environ else os.environ[
        "NBDD_PEERS"].split(",")
    # contains all blocks for all devices as a contiguous list of bytes
    blocks = []
    # a list of all devices so we know the starting offset of a given device in `blocks`
    # (all devices are fixed size)
    volumes = []
    if peers:
        blocks = ReplBlocks()
        volumes = ReplList()
        health_counter = ReplCounter()
        HealthHandler.counter = health_counter
        self_address = "{}:2001".format(os.environ["NBDD_HOSTNAME"])
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
    logging.info("NBD Server Starting with peers {}...".format(peers))
    while True:
        cxn, client = sock.accept()
        logging.info("Connection accepted from client {}".format(client))
        _thread.start_new_thread(handle_cxn, (cxn, blocks, volumes))
        logging.info(
            "Connection closed by client {} -- listening for next client".
            format(client))


if __name__ == "__main__":
    main()
