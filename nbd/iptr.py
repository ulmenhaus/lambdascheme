import collections


class MagicValues(object):
    MinimalClientFlags = b"\x00\x00\x00\x01"  # set high NBD_FLAG_C_FIXED_NEWSTYLE
    OptionRequestPrefix = b"IHAVEOPT"
    OptionResponsePrefix = b"\x00\x03\xe8\x89\x04\x55\x65\xa9"
    OptionsExportName = b"\x00\x00\x00\x01"
    OptionUnsupported = b"\x80\x00\x00\x01"
    RequestPrefix = b"\x25\x60\x95\x13"
    RequestKindRead = b"\x00\x00"
    RequestKindWrite = b"\x00\x01"
    RequestKindClose = b"\x00\x02"
    ResponsePrefix = b"\x67\x44\x66\x98"
    HandshakeMagic = b"NBDMAGICIHAVEOPT"
    HandshakeMinimalFlags = b"\x00\x01"


Option = collections.namedtuple("Option", ("kind", "data"))
TransmissionRequest = collections.namedtuple(
    "TransmissionRequest",
    ("kind", "handle", "offset", "length", "data"),
)


class NBDInterpreter(object):
    def __init__(self, cxn, client=False):
        self._cxn = cxn
        if not client:
            self._handshake()

    def _handshake(self):
        self._cxn.sendall(MagicValues.HandshakeMagic)
        self._cxn.sendall(MagicValues.HandshakeMinimalFlags)
        client_flags = next_n_bytes(self._cxn, 4)
        if client_flags != MagicValues.MinimalClientFlags:
            raise ValueError("Unknown client flags: {}".format(client_flags))

    def get_client_options(self):
        # options
        while True:
            prefix = next_n_bytes(self._cxn, 8)
            if prefix != MagicValues.OptionRequestPrefix:
                raise ValueError(
                    "Unknown prefix in client block: {}".format(prefix))
            option = next_n_bytes(self._cxn, 4)
            data_len = int.from_bytes(next_n_bytes(self._cxn, 4),
                                      byteorder="big")
            data = next_n_bytes(self._cxn, data_len)
            yield Option(option, data)
            if option == MagicValues.OptionsExportName:  # signals transition to transmission phase
                break

    def send_option_unsupported(self, option):
        self._cxn.sendall(MagicValues.OptionResponsePrefix)
        self._cxn.sendall(option.kind)
        self._cxn.sendall(MagicValues.OptionUnsupported)
        self._cxn.sendall(b"\x00" * 4)

    def send_export_response(self, size):
        self._cxn.sendall(size.to_bytes(byteorder="big", length=8))
        # transmission flags
        self._cxn.sendall(b"\x00\x01")
        # Later versions of the nbd kernel module seem to ignore the zero padding even if NBD_OPT_GO
        # is rejected so disabling for now
        #
        # zero padding
        # self._cxn.sendall(b"\x00" * 124)

    def get_transmission_requests(self):
        while True:
            prefix = next_n_bytes(self._cxn, 4)
            if prefix == None:
                break
            if prefix != MagicValues.RequestPrefix:
                raise ValueError("Unknown block prefix: {}".format(prefix))
            flags = next_n_bytes(self._cxn, 2)
            if flags != b"\x00\x00":
                raise ValueError(
                    "Didn't expect any flags for command but got: {}".format(
                        flags))
            req_type = next_n_bytes(self._cxn, 2)
            handle = next_n_bytes(self._cxn, 8)
            offset = int.from_bytes(next_n_bytes(self._cxn, 8),
                                    byteorder="big")
            length = int.from_bytes(next_n_bytes(self._cxn, 4),
                                    byteorder="big")
            data = None
            if req_type == MagicValues.RequestKindWrite and length > 0:
                data = next_n_bytes(self._cxn, length)
            yield TransmissionRequest(req_type, handle, offset, length, data)

    def send_transmission_response(self, handle, data=None):
        self._cxn.sendall(MagicValues.ResponsePrefix)
        self._cxn.sendall(b"\x00\x00\x00\x00")
        self._cxn.sendall(handle)
        if data:
            self._cxn.sendall(data)

    def start_session(self, dev_name):
        magic = next_n_bytes(self._cxn, len(MagicValues.HandshakeMagic))
        if magic != MagicValues.HandshakeMagic:
            raise ValueError("server did not start with proper magic value")
        flags = next_n_bytes(self._cxn, len(MagicValues.HandshakeMinimalFlags))
        if flags != MagicValues.HandshakeMinimalFlags:
            raise ValueError(
                "server did not give the expected handshake flags")
        self._cxn.sendall(MagicValues.MinimalClientFlags)
        self._cxn.sendall(MagicValues.OptionRequestPrefix)
        self._cxn.sendall(MagicValues.OptionsExportName)
        self._cxn.sendall(len(dev_name).to_bytes(byteorder="big", length=4))
        self._cxn.sendall(dev_name)


def next_n_bytes(cxn, n):
    data = b''
    while len(data) < n:
        packet = cxn.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data
