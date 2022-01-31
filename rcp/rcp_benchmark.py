import hashlib
import json
import os
import random
import sys
import threading
import time

import rcp


class PacketCountingMiddleware(object):
    def __init__(self, wrapped, n=2):
        self.wrapped = wrapped
        self.lock = threading.Lock()
        self.total_sends = 0
        self.total_recvs = 0
        self.n = n

    def sendto(self, msg, address):
        with self.lock:
            self.total_sends += 1
        return self.wrapped.sendto(msg, address)

    def recvfrom(self, n):
        with self.lock:
            self.total_recvs += 1
        return self.wrapped.recvfrom(n)

    def fileno(self):
        return self.wrapped.fileno()

    def close(self):
        return self.wrapped.close()


def _log_datum(location, datum, condition):
    results = {}
    if os.path.exists(location):
        with open(location) as f:
            results = json.load(f)
    if condition not in results:
        results[condition] = [datum]
    else:
        results[condition].append(datum)
    with open(location, 'w') as f:
        json.dump(results, f, indent=4)


def main():
    src_addr, src_port, dst_addr, dst_port, condition = sys.argv[1:]
    router = rcp.RCPRouter((src_addr, int(src_port)))
    router.sock = PacketCountingMiddleware(router.sock)
    sock = router.connect((dst_addr, int(dst_port)))

    time_start = time.time()
    random.seed()
    sent_hash = hashlib.sha256()
    sent_len = 0
    for i in range(1000):
        to_send = random.randbytes(random.randrange(200, 400))
        sent_hash.update(to_send)
        sent_len += len(to_send)
        sock.send(to_send)
        time.sleep(random.randrange(2, 20) / 1000)

    recv_hash = hashlib.sha256()
    recv_len = 0
    while recv_len != sent_len:
        msg = sock.recv()
        recv_hash.update(msg)
        recv_len += len(msg)

    total_time_s = time.time() - time_start
    sock.close()
    router.close()

    if recv_hash.hexdigest() == sent_hash.hexdigest():
        print(
            f"Sent and received {sent_len} bytes. Confirmed hashes match: {sent_hash.hexdigest()}"
        )
    else:
        raise ValueError(
            f"Hash mismatch between sent bytes and received bytes: {sent_hash.hexdigest()} != {recv_hash.hexdigest()}"
        )
    print(
        f"Toatal packets sent: {router.sock.total_sends} -- Total packets received: {router.sock.total_recvs}"
    )

    # packets received isn't meaningful here since we don't know how many packets our peer sent
    # so just log the packets sent
    _log_datum("results.json", [router.sock.total_sends, total_time_s], condition)


if __name__ == "__main__":
    main()
