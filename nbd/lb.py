import json
import logging
import os
import random
import socket
import _thread

from nbd.iptr import NBDInterpreter, MagicValues

PROXY_BUFFER_SIZE = 1024


class NBDLoadBalancer(object):
    def __init__(self, shards, socket_descriptor=('0.0.0.0', 2000)):
        self.shards = shards
        self.socket_descriptor = socket_descriptor

    def listen_forever(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(self.socket_descriptor)
        sock.setblocking(True)
        sock.listen(1)

        logging.info("NBD Load Balancer Starting...")
        while True:
            cxn, client = sock.accept()
            logging.info("Connection accepted from client {}".format(client))
            _thread.start_new_thread(self.process_cxn, (cxn, ))

    def process_cxn(self, cxn):
        iptr = NBDInterpreter(cxn)
        volume = None
        for opt in iptr.get_client_options():
            if opt.kind == MagicValues.OptionsExportName:
                volume = opt.data
            else:
                # we don't support any extra options
                logging.info("Ignoring client option: {}".format(opt.kind))
                iptr.send_option_unsupported(opt)
        shard_ix = (hash(volume) % len(self.shards))
        random.seed()
        replica = random.choice(self.shards[shard_ix])
        logging.info(
            "Sending client to replica {} shard {} for volume {}".format(
                replica, shard_ix, volume))
        repl_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        repl_sock.connect((replica, 2000))
        repl_iptr = NBDInterpreter(repl_sock, client=True)
        repl_iptr.start_session(volume)
        _thread.start_new_thread(self.proxy, (cxn, repl_sock))
        self.proxy(repl_sock, cxn)

    def proxy(self, src_sock, dest_sock):
        while True:
            payload = src_sock.recv(PROXY_BUFFER_SIZE)
            if not payload:
                dest_sock.close()
                break
            dest_sock.sendall(payload)


def main():
    # log everything to stderr because compose containers for some reason aren't logging stdout
    logging.basicConfig(level=logging.DEBUG,
                        filename='/proc/self/fd/2',
                        filemode='w')
    shards = json.loads(os.environ["NBD_SHARDS"])
    lb = NBDLoadBalancer(shards)
    lb.listen_forever()


if __name__ == "__main__":
    main()
