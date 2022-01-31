import random
import socket
import threading
import time
import unittest

import rcp


class TestSlidingFencePacket(unittest.TestCase):
    def test_encode_syn(self):
        p = rcp.SlidingFencePacket(
            pckt_type=rcp.SlidingFenceType.SYN,
            seq_number=42,
            acks=[],
            data=b'Hello, world!',
        )
        expected = b'\x01\x00\x00\x00\x2aHello, world!'
        self.assertEqual(expected, p.encode())

    def test_encode_ack(self):
        p = rcp.SlidingFencePacket(
            pckt_type=rcp.SlidingFenceType.ACK,
            seq_number=42,
            acks=[True] * 16 + [False] * 16,
            data=b'',
        )
        expected = b'\x02\x00\x00\x00\x2a\x00\x00\xff\xff'
        self.assertEqual(expected, p.encode())

    def test_decode_syn(self):
        encoded = b'\x01\x00\x00\x00\x2aHello, world!'
        p = rcp.SlidingFencePacket.decode(encoded)
        expected = rcp.SlidingFencePacket(
            pckt_type=rcp.SlidingFenceType.SYN,
            seq_number=42,
            acks=[],
            data=b'Hello, world!',
        )
        self.assertEqual(expected, p)

    def test_decode_ack(self):
        encoded = b'\x02\x00\x00\x00\x2a\x00\x00\xff\xff'
        p = rcp.SlidingFencePacket.decode(encoded)
        expected = rcp.SlidingFencePacket(
            pckt_type=rcp.SlidingFenceType.ACK,
            seq_number=42,
            acks=[True] * 16 + [False] * 16,
            data=b'',
        )
        self.assertEqual(expected, p)


class TestStreamDisassembler(unittest.TestCase):
    def test_write_no_breakdown(self):
        d = rcp.StreamDisassembler(32)
        d.write(b'h' * 31)
        self.assertEqual({}, d.packets)
        self.assertEqual(b'h' * 31, d.buff)
        self.assertEqual(0, d.next_ix)

    def test_write_with_breakdown(self):
        d = rcp.StreamDisassembler(32)
        d.write(b'h' * 31)
        d.write(b'e' * 64)
        expected_packets = {
            0:
            rcp.SlidingFencePacket(
                pckt_type=rcp.SlidingFenceType.SYN,
                seq_number=0,
                acks=[],
                data=b'h' * 31 + b'e',
            ),
            1:
            rcp.SlidingFencePacket(
                pckt_type=rcp.SlidingFenceType.SYN,
                seq_number=1,
                acks=[],
                data=b'e' * 32,
            ),
        }
        self.assertEqual(expected_packets, d.packets)
        self.assertEqual(d.buff, b'e' * 31)
        self.assertEqual(d.next_ix, 2)

    def test_flush_no_finish(self):
        d = rcp.StreamDisassembler(32)
        d.write(b'h' * 31)
        d.flush()
        expected_packets = {
            0:
            rcp.SlidingFencePacket(
                pckt_type=rcp.SlidingFenceType.SYN,
                seq_number=0,
                acks=[],
                data=b'h' * 31,
            ),
        }
        self.assertEqual(expected_packets, d.packets)
        self.assertEqual(d.buff, b'')
        self.assertEqual(d.next_ix, 1)

    def test_flush_with_finish(self):
        d = rcp.StreamDisassembler(32)
        d.write(b'h' * 31)
        d.flush(True)
        expected_packets = {
            0:
            rcp.SlidingFencePacket(
                pckt_type=rcp.SlidingFenceType.SYN,
                seq_number=0,
                acks=[],
                data=b'h' * 31,
            ),
            1:
            rcp.SlidingFencePacket(
                pckt_type=rcp.SlidingFenceType.FIN,
                seq_number=1,
                acks=[],
                data=b'',
            ),
        }
        self.assertEqual(expected_packets, d.packets)
        self.assertEqual(d.buff, b'')
        self.assertEqual(d.next_ix, 2)


class TestRCPRouter(unittest.TestCase):
    def test_e2e_single_session_small_message_client_close(self):
        server = rcp.RCPRouter(("127.0.0.1", 12345))
        client = rcp.RCPRouter(("127.0.0.1", 12346))

        server.listen()

        client_sock = client.connect(("127.0.0.1", 12345))
        server_sock = server.accept()

        client_sock.send(b'Hello, server!')
        self.assertEqual(b'Hello, server!', server_sock.recv())

        server_sock.send(b'Hello, client!')
        self.assertEqual(b'Hello, client!', client_sock.recv())

        client_sock.close()
        self.assertEqual(b'', client_sock.recv())
        self.assertEqual(b'', server_sock.recv())

        server.close()
        client.close()

    def test_e2e_single_session_small_message_server_close(self):
        server = rcp.RCPRouter(("127.0.0.1", 12345))
        client = rcp.RCPRouter(("127.0.0.1", 12346))

        server.listen()

        client_sock = client.connect(("127.0.0.1", 12345))
        server_sock = server.accept()

        client_sock.send(b'Hello, server!')
        self.assertEqual(b'Hello, server!', server_sock.recv())

        server_sock.send(b'Hello, client!')
        self.assertEqual(b'Hello, client!', client_sock.recv())

        server_sock.close()
        self.assertEqual(b'', client_sock.recv())
        self.assertEqual(b'', server_sock.recv())

        server.close()
        client.close()

    def test_e2e_multi_session_small_message_client_close(self):
        server = rcp.RCPRouter(("127.0.0.1", 12345))
        client_a = rcp.RCPRouter(("127.0.0.1", 12346))
        client_b = rcp.RCPRouter(("127.0.0.1", 12347))

        server.listen()

        client_a_sock = client_a.connect(("127.0.0.1", 12345))
        server_a_sock = server.accept()
        client_b_sock = client_b.connect(("127.0.0.1", 12345))
        server_b_sock = server.accept()

        client_a_sock.send(b'Hello, server from client a!')
        client_b_sock.send(b'Hello, server from client b!')

        self.assertEqual(b'Hello, server from client b!', server_b_sock.recv())
        self.assertEqual(b'Hello, server from client a!', server_a_sock.recv())

        server_a_sock.send(b'Hello, client a!')
        server_b_sock.send(b'Hello, client b!')
        self.assertEqual(b'Hello, client a!', client_a_sock.recv())
        self.assertEqual(b'Hello, client b!', client_b_sock.recv())

        client_a_sock.close()
        client_b_sock.close()

        self.assertEqual(b'', client_a_sock.recv())
        self.assertEqual(b'', server_a_sock.recv())
        self.assertEqual(b'', client_b_sock.recv())
        self.assertEqual(b'', server_b_sock.recv())

        server.close()
        client_a.close()
        client_b.close()

    def test_e2e_single_session_large_message_client_close(self):
        server = rcp.RCPRouter(("127.0.0.1", 12345))
        client = rcp.RCPRouter(("127.0.0.1", 12346))

        server.listen()

        client_sock = client.connect(("127.0.0.1", 12345))
        server_sock = server.accept()

        random.seed()

        client_message = random.randbytes(
            10 * 128 * 32)  # should ensure 10 sliding windows
        client_sock.send(client_message)

        server_message = random.randbytes(
            10 * 128 * 32)  # should ensure 10 sliding windows
        server_sock.send(server_message)

        client_sock.close()

        server_received = server_sock.read()
        self.assertEqual(client_message, server_received)

        client_received = client_sock.read()
        self.assertEqual(server_message, client_received)

        server.close()
        client.close()

    def test_e2e_single_session_large_message_over_faulty_socket(self):
        server = rcp.RCPRouter(("127.0.0.1", 12345))
        client = rcp.RCPRouter(("127.0.0.1", 12346))

        server.sock = FaultySocket(server.sock)
        client.sock = FaultySocket(client.sock)

        server.listen()

        client_sock = client.connect(("127.0.0.1", 12345))
        server_sock = server.accept()

        random.seed()

        client_message = random.randbytes(
            10 * 128 * 32)  # should ensure 10 sliding windows
        client_sock.send(client_message)

        server_message = random.randbytes(
            10 * 128 * 32)  # should ensure 10 sliding windows
        server_sock.send(server_message)

        client_sock.close()

        server_received = server_sock.read()
        self.assertEqual(client_message, server_received)

        client_received = client_sock.read()
        self.assertEqual(server_message, client_received)

        # because the last ack will likely be dropped, give both sides adequate time to
        # close by time out
        time.sleep(.3)
        self.assertEqual({}, client.sessions)
        self.assertEqual({}, server.sessions)

        server.close()
        client.close()


class FaultySocket(object):
    def __init__(self, wrapped, n=2):
        self.wrapped = wrapped
        self.lock = threading.Lock()
        self.total_sends = 0
        self.n = n

    def sendto(self, msg, address):
        with self.lock:
            self.total_sends += 1
        if not random.randrange(0, self.n):
            return self.wrapped.sendto(msg, address)

    def recvfrom(self, n):
        return self.wrapped.recvfrom(n)

    def fileno(self):
        return self.wrapped.fileno()

    def close(self):
        return self.wrapped.close()
