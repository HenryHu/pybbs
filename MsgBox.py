#!/usr/bin/env python
from Util import Util
from User import User
from MsgHead import MsgHead
import struct

class MsgBox:
    name = ''
    fAll = None
    fIn = None
    fContent = None

    def __init__(self, username):
        self.name = username

    def LockGeneral(self, file, write):
        if (write):
            return Util.WLockFile(file)
        else:
            return Util.RLockFile(file)

    def LockAll(self, write):
        if (self.fAll == None):
            if (not self.OpenAll(write)):
                return False

        return self.LockGeneral(self.fAll, write)

    def LockIn(self, write):
        if (self.fIn == None):
            if (not self.OpenIn(write)):
                return False

        return self.LockGeneral(self.fIn, write)

    def LockContent(self, write):
        if (self.fContent == None):
            if (not self.OpenContent(write)):
                return False

        return self.LockGeneral(self.fContent, write)

    def UnlockGeneral(self, file):
        if (file != None):
            return Util.UnlockFile(file)
        else:
            return True # maybe not ok!

    def UnlockAll(self):
        return self.UnlockGeneral(self.fAll)

    def UnlockIn(self):
        return self.UnlockGeneral(self.fIn)

    def UnlockContent(self):
        return self.UnlockGeneral(self.fContent)

    def OpenGeneral(self, file, write):
        path = User.OwnFile(self.name, file)
        if (write):
            return open(path, 'r+b')
        else:
            return open(path, 'rb')

    def OpenIn(self, write):
        self.fIn = self.OpenGeneral('msgindex2', write)
        return (self.fIn != None)

    def OpenAll(self, write):
        self.fAll = self.OpenGeneral('msgindex', write)
        return (self.fAll != None)

    def OpenContent(self):
        self.fContent = self.OpenGeneral('msgcontent', write)
        return (self.fContent != None)

    def CloseIn(self):
        self.fIn.close()

    def CloseAll(self):
        self.fAll.close()

    def CloseContent(self):
        self.fContent.close()


    def SizeIn(self):
        return Util.SizeGeneral(self.fIn)

    def SizeAll(self):
        return Util.SizeGeneral(self.fAll)

    def SizeContent(self):
        return Util.SizeGeneral(self.fContent)

    def GetUnreadCount(self):
        if (not self.OpenIn(write = False)):
            return -1
        if (not self.LockIn(write = False)):
            self.CloseIn()
            return -1
        size = self.SizeIn()
        count = (size - 4) / MsgHead.size()
        if (size <= 0):
            ret = 0
        else:
            ret = struct.unpack('=i', self.fIn.read(4))[0]
            if (ret >= count):
                ret = 0
            else:
                ret = count - ret

        self.UnlockIn()
        self.CloseIn()
        return ret

    def GetUnreadMsg(self):
        if (not self.OpenIn(write = True)):
            return -1
        if (not self.LockIn(write = True)):
            self.CloseIn()
            return -1
        size = self.SizeIn()
        count = (size - 4) / MsgHead.size()
        if (size <= 0):
            ret = -1
        else:
            ret = struct.unpack('=i', self.fIn.read(4))[0]
            if (ret >= count):
                ret = -1
            else:
                index = ret + 1
                fIn.seek(0)
                fIn.write(struct.pack('=i', index))

        self.UnlockIn()
        self.CloseIn()
        return ret

    def LoadMsgHead(self, index, all):
        if (all):
            if (not self.OpenAll(write = False)):
                return None
        else:
            if (not self.OpenIn(write = False)):
                return None
            
        if (all):
            file = self.fAll
        else:
            file = self.fIn

        if (not self.LockGeneral(file, write = False)):
            self.CloseIn()
            return None
        size = Util.SizeGeneral(file)

        count = (size - 4) / MsgHead.size()
        if (index < 0 or index >= count):
            self.UnlockGeneral(file)
            file.close()
            return None

        file.seek(index * MsgHead.size() + 4)
        ret = MsgHead(file.read(MsgHead.size()))

        self.UnlockGeneral(file)
        file.close()
        return ret

