from Util import Util
import Config
import struct

class Friend:
    """struct friends
    the entries of HOME/friends"""
    _parser = struct.Struct('=%ds%ds' % (13, Config.LEN_FRIEND_EXP))
    _fields = [['id', 1], ['exp', 1]]

    size = _parser.size

    def unpack(self, str):
        Util.Unpack(self, Friend._parser.unpack(str))

    def pack(self):
        return Friend._parser.pack(*Util.Pack(self))

    def __init__(self, str):
        self.unpack(str)

    def NCaseId(self):
        return self._id.lower
