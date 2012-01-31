#!/usr/bin/env python
import struct
import Config
from Util import Util

class MsgHead:
    parser = struct.Struct('=iibb%dsiii' % (Config.IDLEN + 2))
    _fields = ['pos', 'len', 'sent', 'mode', ['id', 1], 'time', 'frompid', 'topid']

    #struct msghead
    size = parser.size
    
    def unpack(self, str):
        Util.Unpack(self, MsgHead.parser.unpack(str))

    def pack(self):
        return MsgHead.parser.pack(*Util.Pack(self))

    def __init__(self, str):
        self.unpack(str)


