import functools
import logging
import sys
import threading

import rcp

logger = logging.getLogger()


def _serve_sock(sock):
    while msg := sock.recv():
        sock.send(msg)
    sock.close()


def listen_and_serve(router):
    while True:
        sock = router.accept()
        threading.Thread(target=functools.partial(_serve_sock, sock)).start()


def main():
    logging.basicConfig(level=logging.DEBUG)
    addr, port = sys.argv[1:]
    router = rcp.RCPRouter((addr, int(port)))
    logger.info(f"Starting RCP Echo Server at {addr}:{port}")
    router.listen()
    listen_and_serve(router)


if __name__ == "__main__":
    main()
