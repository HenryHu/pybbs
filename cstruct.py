from Util import Util

class CStruct(object):
    def unpack(self, data):
        Util.Unpack(self, self.parser.unpack(data))

    def pack(self):
        return self.parser.pack(*Util.Pack(self))

    def __init__(self, data = None):
        if (data == None):
            Util.InitStruct(self)
        else:
            self.unpack(data)
