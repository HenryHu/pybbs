#!/usr/bin/env python

# from Log import Log
import codecs
import random
import struct
import fcntl
import os
import stat
import mmap
import string
import re
import hashlib
import Defs

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
                    setattr(obj, fields[i][0], list(struct.unpack(fields[i][2], data[i])))
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
                    if (len(fields[i]) >= 3):
                        # terminal zero
                        ret.append(getattr(obj, fields[i][0])[:fields[i][2]-1])
                    else:
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
        line = ''
        while 1:
            c = fp.read(1)
            if (c == '\0'):
                break
            if (c == ''):
                break
            line += c
        return line

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
        if (fstat.st_size < 0):
            fd.close()
            return None
        return mmap.mmap(fd.fileno(), fstat.st_size, flags = flag, prot = pro)

    @staticmethod
    def GetRecordCount(path, size):
        try:
            st = os.stat(path)
            return st.st_size / size;
        except OSError:
#            Log.error("fail to get record count: %s" % path)
            return -1

    @staticmethod
    def GetRecords(path, size, index, count):
        ret = []
        fp = open(path, 'r+b')
        fp.seek(size * (index - 1))
        for i in range(count):
            ret.append(fp.read(size))
        return ret

    @staticmethod
    def SHMGetString(shm, offset, size):
        return Util.CString(shm.read(size, offset))

    @staticmethod
    def SHMGetVal(shm, offset, format, size=0):
        if (size == 0):
            return struct.unpack(format, shm.read(struct.calcsize(format), offset))[0]
        else:
            return struct.unpack(format, shm.read(size, offset))[0]

    @staticmethod
    def SHMPutVal(shm, offset, val, format):
        return shm.write(struct.pack(format, val), offset)

    @staticmethod
    def SHMGetInt(shm, offset):
        return Util.SHMGetVal(shm, offset, '=i', 4)

    @staticmethod
    def SHMGetUInt(shm, offset):
        return Util.SHMGetVal(shm, offset, '=I', 4)

    @staticmethod
    def SHMPutInt(shm, offset, val):
        return Util.SHMPutVal(shm, offset, val, '=i')

    @staticmethod
    def SHMPutUInt(shm, offset, val):
        return Util.SHMPutVal(shm, offset, val, '=I')

    @staticmethod
    def RemoveTags(str):
        ret = ''
        intag = False
        for ch in str:
            if (intag):
                if (ch.isalpha()):
                    intag = False
            else:
                if (ch == '\033'):
                    intag = True
                else:
                    ret += ch
        return ret

    @staticmethod
    def AppendRecord(filename, record):
        try:
            with open(filename, "ab") as f:
                os.fchmod(f.fileno(), 0664)
                fcntl.flock(f, fcntl.LOCK_EX)
                # no lseek: append
                try:
                    f.write(record)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except IOError:
            return -1

        return 0

    @staticmethod
    def SeekInFile(filename, str):
        try:
            with open(filename, "r") as f:
                line = f.readline()
                while (line != ""):
                    line = re.split('[: \n\r\t]', line)[0]
                    if (line.lower() == str.lower()):
                        return True
                    line = f.readline()
        except IOError:
            return False
        return False

    @staticmethod
    def InitFields(cls):
        base = 0
        for field in cls._fields:
            name = field[0]
            ftype = field[1]
            size = ftype.size
            ftype.setbase(base)
            base += size
            setattr(cls, name, ftype)
        cls.size = base

    @staticmethod
    def HashGen(data, key):
        ''' igenpass() '''
        m = hashlib.md5()
        m.update(Defs.PASSMAGIC)
        m.update(data)
        m.update(Defs.PASSMAGIC)
        m.update(key)
        return m.digest()

def fixterm_handler(exc):
    fixterm_debug = False
    if isinstance(exc, (UnicodeDecodeError)):
        s = u""
        lc = 0
        ci = 0
        cr = 0
        pos = exc.start
        for c in exc.object[exc.start:]:
            pos = pos + 1
            if (ci == 0):
                if fixterm_debug: print "State: initial"
                if (ord(c) < 128):
                    if fixterm_debug: print "ASCII"
                    s += c
                    break
                elif (ord(c) == 128):
                    # hack: gbk does not allow 0x80
                    # but microsoft made it a euro sign
                    s += u'\u20ac'
                    break
                else:
                    if fixterm_debug: print "Got first half"
                    ci = 1
            elif (ci == 1):
                if fixterm_debug: print "State: after first half"
                if (ord(c) < 0x40): 
                    if (ord(c) == 0x1b):# \ESC
                        if fixterm_debug: print "Got tag inside. First half:", lc
                        cr = lc
                        s += c
                        s += "[50m"
                        s += c
                        ci = 2
                    else:
                        if fixterm_debug: print "Unknown thing inside...", c
                        s += c
                        ci = 0
                        break
                else:
                    if fixterm_debug: print "Got second half. decode."
                    ci = 0
                    sx = ""
                    sx += chr(lc)
                    sx += c
                    s += sx.decode("gbk", "ignore")
                    break
            elif (ci == 2): # '['
                if fixterm_debug: print "[", ord(c)
                s += c
                ci = 3
            elif (ci == 3): # 'i;jm'
                if fixterm_debug: print "num: ", ord(c)
                s += c
                if ((ord(c) >= 64) and (ord(c) <= 126)):
                    ci = 4
            elif (ci == 4): # another half
                if fixterm_debug: print "ANOTHER", ord(c), " first:", cr
                sx = ""
                sx += chr(cr)
                sx += c
                try:
                    s += sx.decode("gbk")
                except:
                    s += '?'
                break

            lc = ord(c)
        return (s, pos)

codecs.register_error("fixterm", fixterm_handler)
