import enum
import random
import socket
import sys
import threading
import time

ETH_P_ALL = 3


class Router(object):
    def __init__(self, ifaces, route_rules):
        self.ifaces = ifaces
        self.route_rules = route_rules
        self.iface2sock = {}

    def start_routing(self):
        for iface in self.ifaces:
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                 socket.htons(ETH_P_ALL))
            self.iface2sock[iface] = sock
            thread = threading.Thread(target=lambda: self._listen_from(iface))
            thread.start()

    def _listen_from(self, iface):
        sock = self.iface2sock[iface]
        sock.bind((iface, 0))
        # TODO should be max IP packet size
        while True:
            packet = IPPacket.from_bytes(sock.recv(64))
            dst_dotdec = packet.dst_addr.to_dotdec()
            if dst_dotdec not in self.route_rules:
                continue
            # TODO generalize, but testing for now
            if random.choice([True, False]):
                continue
            dst = self.iface2sock[self.route_rules[dst_dotdec]]
            dst.send(packet.to_bytes())


class IPAddr(object):
    def __init__(self, dotdec):
        self._bytes = self._addr2bytes(dotdec)

    def to_bytes(self):
        return self._bytes

    @classmethod
    def from_bytes(cls, b):
        return cls(cls._bytes2addr(b))

    def to_dotdec(self):
        return self._bytes2addr(self._bytes)

    @staticmethod
    def _addr2bytes(addr):
        parts = list(map(int, addr.split(".")))
        return ''.join(map(chr, parts)).encode("latin")

    @staticmethod
    def _bytes2addr(b):
        return ".".join(str(ord(c)) for c in b.decode("latin"))


class IPPacket(object):
    def __init__(self, src_addr, dst_addr, data):
        self.src_addr = src_addr
        self.dst_addr = dst_addr
        self.data = data

    def to_bytes(self):
        return self.src_addr.to_bytes() + self.dst_addr.to_bytes() + self.data

    @classmethod
    def from_bytes(cls, b):
        src_addr, dst_addr, data = b[0:4], b[4:8], b[8:]
        return cls(
            IPAddr.from_bytes(src_addr),
            IPAddr.from_bytes(dst_addr),
            data,
        )


class IPDump(object):
    def __init__(self, dev, src):
        self.dev = dev
        self.src = src

    def start(self):
        thread = threading.Thread(target=self._dump)
        thread.start()

    def _dump(self):
        sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                             socket.htons(ETH_P_ALL))
        sock.bind((self.dev, 0))
        while True:
            packet = IPPacket.from_bytes(sock.recv(64))
            if self.src != packet.src_addr.to_dotdec():
                continue
            print("{} got packet from {}: {}".format(
                self.dev, packet.src_addr.to_dotdec(), packet.data))


class IPCxn(object):
    def __init__(self, src_addr_dotdec, dst_addr_dotdec, dev):
        self.src_addr = IPAddr(src_addr_dotdec)
        self.dst_addr = IPAddr(dst_addr_dotdec)
        self.dev = dev
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                  socket.htons(ETH_P_ALL))
        self.sock.bind((dev, 0))

    def send_data(self, data):
        packet = IPPacket(self.src_addr, self.dst_addr, data)
        self.sock.send(packet.to_bytes())

    def recv_data(self):
        while True:
            packet = IPPacket.from_bytes(self.sock.recv(64))
            if self.dst_addr.to_bytes() != packet.src_addr.to_bytes():
                continue
            return packet.data


class RCPPacketType(enum.Enum):
    SYN = 1
    ACK = 2


class RCPPacket(object):
    def __init__(self, ptype, index, acks, data):
        assert len(acks) == 32
        self.ptype = ptype
        self.index = index
        self.acks = acks
        self.data = data

    def to_bytes(self):
        acks_int = sum(int(self.acks[i]) << i for i in range(len(self.acks)))
        return self.ptype.value.to_bytes(byteorder='big', length=1) + \
            self.index.to_bytes(byteorder='big', length=4) + \
            acks_int.to_bytes(byteorder='big', length=4) + \
            self.data

    @classmethod
    def from_bytes(cls, b):
        ptype_int = int.from_bytes(b[0:1], byteorder='big')
        index_int = int.from_bytes(b[1:5], byteorder='big')
        acks_int = int.from_bytes(b[5:9], byteorder='big')
        data = b[9:]
        return cls(
            RCPPacketType(ptype_int),
            index_int,
            [bool((acks_int >> i) & 1) for i in range(32)],
            data,
        )


class RCPCxn(object):
    def __init__(self, ipcxn, timeout=.1):
        self.ipcxn = ipcxn
        self.send_ix = 0  # index of the next addition to the queue
        self.send_queue = []
        self.recv_ix = 0  # index of the first entry in the queue
        self.recv_queue = [None] * 32
        self.timeout = timeout
        self.lock = threading.Lock()

    def start(self):
        threading.Thread(target=self._send_loop).start()
        threading.Thread(target=self._recv_loop).start()

    def _send_loop(self):
        while True:
            # only send within 32 packets of the lowest one because the other
            # end will discard anything else
            to_send = []
            with self.lock:
                for packet in self.send_queue:
                    if not to_send:
                        to_send.append(packet)
                    elif (packet.index - to_send[0].index) < 32:
                        to_send.append(packet)
            for packet in to_send:
                self.ipcxn.send_data(packet.to_bytes())
            self.ipcxn.send_data(self._ack_packet().to_bytes())
            time.sleep(self.timeout)

    def _ack_packet(self):
        acks = [(self.recv_queue[i] is not None) for i in range(32)]
        return RCPPacket(
            RCPPacketType.ACK,
            self.recv_ix,
            acks,
            b'',
        )

    def _recv_loop(self):
        while True:
            packet = RCPPacket.from_bytes(self.ipcxn.recv_data())
            if packet.ptype == RCPPacketType.SYN:
                with self.lock:
                    ix = packet.index - self.recv_ix
                    if ix >= 32 or ix < 0:
                        # disregard as it's outside our current window
                        continue
                    self.recv_queue[ix] = packet
            elif packet.ptype == RCPPacketType.ACK:
                with self.lock:
                    for i in range(len(self.send_queue) - 1, -1, -1):
                        q_packet = self.send_queue[i]
                        if q_packet.index < packet.index:
                            del self.send_queue[i]
                        if (q_packet.index - packet.index) < 32:
                            if packet.acks[q_packet.index - packet.index]:
                                del self.send_queue[i]

    def send(self, data):
        with self.lock:
            packet = RCPPacket(
                RCPPacketType.SYN,
                self.send_ix,
                [True] * 32,
                data,
            )
            self.send_queue.append(packet)
            self.send_ix += 1

    def recv(self):
        while True:
            data = b''
            with self.lock:
                while self.recv_queue[0] is not None:
                    packet = self.recv_queue.pop(0)
                    self.recv_queue.append(None)
                    self.recv_ix += 1
                    data += packet.data
            if data:
                yield data
            time.sleep(.1)


def main():
    random.seed()
    route_rules = {
        "192.168.1.1": "veth1",
        "192.168.1.2": "veth2",
    }
    router = Router(["veth1", "veth2"], route_rules)
    router.start_routing()

    # IPDump("veth0", "192.168.1.2").start()
    # IPDump("veth3", "192.168.1.1").start()

    # Let the threads all initialize properly
    time.sleep(1)

    ip1 = IPCxn("192.168.1.1", "192.168.1.2", "veth0")
    ip2 = IPCxn("192.168.1.2", "192.168.1.1", "veth3")

    #for _ in range(100):
    #    ip1.send_data(b'Hello from veth0')
    #    ip2.send_data(b'Hello from veth1')

    rcp1 = RCPCxn(ip1)
    rcp1.start()
    rcp2 = RCPCxn(ip2)
    rcp2.start()
    # Let the threads all initialize properly
    time.sleep(1)
    for i in range(100):
        rcp1.send('\n\tHello #{} from veth0'.format(i).encode("utf-8"))
    for data in rcp2.recv():
        print("Got data: {}".format(data.decode("utf-8")))


if __name__ == "__main__":
    main()
