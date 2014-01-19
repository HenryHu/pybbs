from Util import Util
import struct

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

class InmemStruct(object):
    def __init__(self):
        self.value = ['\0'] * self.size

    def read(self, pos, len):
        return "".join(self.value[pos:pos+len])

    def write(self, pos, data):
        self.value[pos:pos+len(data)] = list(data)


class Field(object):
    def __init__(self):
        self._parser = struct.Struct(self._format)
        self._base = 0

    def setbase(self, base):
        self._base = base

    def __get__(self, obj, objtype):
        return self._parser.unpack(obj.read(self._base, self._parser.size))[0]

    def __set__(self, obj, val):
        obj.write(self._base, self._parser.pack(val))

    @property
    def size(self):
        return self._parser.size

class I8(Field):
    _format = '=b'

class U8(Field):
    _format = '=B'

class I32(Field):
    _format = '=i'

class U32(Field):
    _format = '=I'

class FixStr(Field):
    def __init__(self, len):
        self._format = "%ds" % len
        Field.__init__(self)

class Str(FixStr):
    def __init__(self, len):
        FixStr.__init__(self, len)

    # no problem in __set__: auto pad 0
    def __get__(self, obj, val):
        return Util.CString(Field.__get__(self, obj, val))

class Array(object):
    def __init__(self, childtype, count):
        self.childtype = childtype
        self.children = []
        for i in range(0, count):
            self.children.append(childtype())
        self._base = 0

    def __get__(self, obj, objtype):
        # the point is to pass obj to __get__
        return ArrayWithOwner(self, obj, objtype)

    def setbase(self, base):
        self._base = base
        i = 0
        for child in self.children:
            child.setbase(base + child.size * i)
            i += 1

    @property
    def size(self):
        if (len(self.children) > 0):
            return len(self.children) * self.children[0].size
        else:
            return 0

class ArrayWithOwner(object):
    def __init__(self, array, obj, objtype):
        self.array = array
        self.obj = obj
        self.objtype = objtype

    def __getitem__(self, index):
        return self.array.children[index].__get__(self.obj, self.objtype)

    def __setitem__(self, index, val):
        return self.array.children[index].__set__(self.obj, val)

    @property
    def _base(self):
        return self.array._base

    @property
    def size(self):
        return self.array.size

def init_fields(cls):
    Util.InitFields(cls)
    return cls
