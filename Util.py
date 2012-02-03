#!/usr/bin/env python

import codecs
import random
import struct
import fcntl
import os
import stat
import mmap
import string

class Util:
    gbkDecoder = codecs.getdecoder('gbk')
    gbkEncoder = codecs.getencoder('gbk')
    utfDecoder = codecs.getdecoder('utf-8')
    utfEncoder = codecs.getencoder('utf-8')
    random = random.Random()

    @staticmethod
    def gbkDec(string):
        return Util.gbkDecoder(string, errors='fixterm')[0]

    @staticmethod
    def gbkEnc(string):
        return Util.gbkEncoder(string, errors='ignore')[0]

    @staticmethod
    def utfDec(string):
        return Util.utfDecoder(string, errors='ignore')[0]

    @staticmethod
    def utfEnc(string):
        return Util.utfEncoder(string, errors='ignore')[0]

    @staticmethod
    def CheckRange(start, end, count, defcount, maxend):
        '''start
        end
        count

        ---: Last, default count
        --+: Last
        -+-: To end, default count
        -++: To end
        +--: From start, default count
        +-+: From start
        ++-: From start, to end
        +++: Illegal
    '''    

        if (count == 0):
            if ((start != 0) and (end != 0)):
                count = end - start + 1
            else:
                count = defcount
        if (start != 0):
            if (end == 0):
                end = min(start + count - 1, maxend)
        else:
            if (end == 0):
                end = maxend
            start = max(1, end - count + 1)

        return start, end

    @staticmethod
    def GetInt(params, name, defval = 0):
        if (params.has_key(name)):
            return int(params[name])
        else:
            return defval
    
    @staticmethod
    def GetString(params, name, defval = ''):
        if (params.has_key(name)):
            return params[name]
        else:
            return defval

    @staticmethod
    def Unpack(obj, data):
        Util.UnpackX(obj, data, obj._fields)

    @staticmethod
    def UnpackX(obj, data, fields):
        if (len(data) != len(fields)):
            raise Exception("Unpack: count mismatch!")
        for i in range(0, len(fields)):
            if (type(fields[i]) == type(list())):
                if (fields[i][1] == 1):
                    setattr(obj, fields[i][0], Util.CString(data[i]))
                if (fields[i][1] == 2):
                    setattr(obj, fields[i][0], struct.unpack(fields[i][2], data[i]))
            else:
                setattr(obj, fields[i], data[i])

    @staticmethod
    def Pack(obj):
        return Util.PackX(obj, obj._fields)

    @staticmethod
    def PackX(obj, fields):
        ret = []
        for i in range(0, len(fields)):
            if (type(fields[i]) == type(list())):
                if (fields[i][1] == 1):
                    ret.append(getattr(obj, fields[i][0]))
                if (fields[i][1] == 2):
                    ret.append(struct.pack(fields[i][2], *getattr(obj, fields[i][0])))
            else:
                ret.append(getattr(obj, fields[i]))
        return ret

    @staticmethod
    def InitStruct(obj):
        obj.unpack('\0' * obj.size)
#        fields = obj._fields
#        for i in range(len(fields)):
#            if (type(fields[i]) == type(list())):
#                if (fields[i][1] == 1):
#                    setattr(obj, fields[i][0], '')
#                elif (fields[i][1] == 2):
#                    setattr(obj, fields[i][0], [])
#            else:
#                setattr(obj, fields[i], 0)

    @staticmethod
    def CString(string):
        i = string.find('\0')
        if (i != -1):
            return string[:i]
        else:
            return string

    @staticmethod
    def ReadString(fp):
        str = ''
        while 1:
            c = fp.read(1)
            if (c == '\0'):
                break
            if (c == ''):
                break
            str += c
        return str

    @staticmethod
    def RandomStr(len):
        ret = ''
        for i in range(0, len):
            randchr = Util.random.randint(48, 109)
            if (randchr > 57):
                if (randchr > 83):
                    randchr = randchr + 13
                else:
                    randchr = randchr + 7
            ret = ret + chr(randchr)
        return ret

    @staticmethod
    def RandomInt(len):
        return ''.join(random.choice(string.digits) for x in range(len))

    @staticmethod
    def FLock(file, shared = False, nonBlock = False):
        fcntl.flock(file, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | (fcntl.LOCK_NB if nonBlock else 0));

    @staticmethod
    def FUnlock(file):
        fcntl.flock(file, fcntl.LOCK_UN)

    @staticmethod
    def LockFile(file, op):
        lockdata = struct.pack('hhllhh', op, 0, 0, 0, 0, 0)
        ret = fcntl.fcntl(file, fcntl.F_SETLKW, lockdata)
        return (ret != -1)

    @staticmethod
    def RLockFile(file):    # file: file descriptor
        return Util.LockFile(file, fcntl.F_RDLCK)

    @staticmethod
    def WLockFile(file):
        return Util.LockFile(file, fcntl.F_WRLCK)

    @staticmethod
    def UnlockFile(file):
        return Util.LockFile(file, fcntl.F_UNLCK)

    @staticmethod
    def SizeGeneral(file):
        return os.fstat(file.fileno()).st_size

    @staticmethod
    def GetSize(path):
        try:
            return os.stat(path).st_size
        except:
            return -1

    @staticmethod
    def ReadInt(fd):
        return struct.unpack('=i', fd.read(4))[0]

    @staticmethod
    def ReadChar(fd):
        return struct.unpack('=b', fd.read(1))[0]

    @staticmethod
    def Mmap(fd, pro, flag):
        if (fd.fileno() < 0):
            return None
        fstat = os.fstat(fd.fileno())
        if (fstat == None):
            fd.close()
            return None
        if (not stat.S_ISREG(fstat.st_mode)):
            fd.close()
            return None
        if (stat.st_size < 0):
            fd.close()
            return None
        return mmap.mmap(fd.fileno(), fstat.st_size, flags = flag, prot = pro)

    @staticmethod
    def GetRecordCount(path, size):
        try:
            st = os.stat(path)
            return st.st_size / size;
        except Error:
            return -1

    @staticmethod
    def GetRecords(path, size, index, count):
        ret = []
        file = open(path, 'r+b')
        file.seek(size * (index - 1))
        for i in range(count):
            ret.append(file.read(size))
        return ret

def fixterm_handler(exc):
    if isinstance(exc, (UnicodeDecodeError)):
        s = u""
        lc = 0
        ci = 0
        cr = 0
        pos = exc.start
        for c in exc.object[exc.start:]:
            pos = pos + 1
            if (ci == 0):
                if (ord(c) <= 128):
                    s += c
                    break
                else:
                    ci = 1
            elif (ci == 1):
                if (ord(c) < 0x40): 
                    if (ord(c) == 0x1b):# \ESC
                        cr = lc
                        s += c
                        ci = 2
                    else:
                        s += c
                        ci = 0
                        break
#                    print "ESC", cr
                else:
                    ci = 0
                    sx = ""
                    sx += chr(lc)
                    sx += c
                    s += sx.decode("gbk", "ignore")
                    break
            elif (ci == 2): # '['
#                print "[", ord(c)
                s += c
                ci = 3
            elif (ci == 3): # 'i;jm'
#                print "num: ", ord(c)
                s += c
                if ((ord(c) >= 64) and (ord(c) <= 126)):
                    ci = 4
            elif (ci == 4): # another half
#                print "ANOTHER", ord(c)
                sx = ""
                sx += chr(cr)
                sx += c
                s += sx.decode("gbk")
                break

            lc = ord(c)
        return (s, pos)

codecs.register_error("fixterm", fixterm_handler)
