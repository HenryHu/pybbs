#!/usr/bin/env python
from Util import Util
from User import User
from MsgHead import MsgHead
import Config
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
            try:
                return open(path, 'r+b')
            except IOError:
                try:
                    return open(path, 'w+b')
                except:
                    return None
            except:
                return None
        else:
            try:
                return open(path, 'rb')
            except:
                return None

    def OpenIn(self, write):
        self.fIn = self.OpenGeneral('msgindex2', write)
        return (self.fIn != None)

    def OpenAll(self, write):
        self.fAll = self.OpenGeneral('msgindex', write)
        return (self.fAll != None)

    def OpenContent(self, write):
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
                self.fIn.seek(0)
                self.fIn.write(struct.pack('=i', index))

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

    def SaveMsgText(self, msghead, msg):
        if (not self.OpenAll(write = True)):
            return -1;
        if (not self.OpenContent(write = True)):
            self.CloseAll();
            return -1;
        if (not self.LockAll(write = True)):
            self.CloseAll();
            self.CloseContent();
            return -1;
        content_size = self.sizeContent();
        idx_size = self.sizeAll();
        count = 0;
        i = 0;
        if (idx_size <= 0):
            self.fAll.write('\0\0\0\0');
        else:
            count = (idx_size - 4) / MsgHead.size();

        self.fAll.seek(count * MsgHead.size() + 4);
        msglen = len(msg) + 1;
        if (msglen >= Config.MAX_MSG_SIZE):
            msglen = Config.MAX_MSG_SIZE - 1;
        msghead.pos = content_size;
        msghead.len = msglen;

        self.fAll.write(msghead.pack);
        self.fContent.seek(content_size);
        if (msglen != len(msg) + 1):
            self.fContent.write(msg[:msglen]);
        else:
            self.fContent.write(msg);
            self.fContent.write('\0');

        self.CloseContent();
        self.UnlockAll();
        self.CloseAll();

        if (not msghead.sent):
            if (not self.OpenIn(write = True)):
                return -1;
            if (not self.LockIn(write = True)):
                self.CloseIn();
                return -1;
            inbox_size = self.SizeIn();
            inbox_count = 0;
            if (inbox_size <= 0):
                self.fIn.write('\0\0\0\0');
            else:
                inbox_count = (inbox_size - 4) / MsgHead.size();

            self.fIn.seek(inbox_count * MsgHead.size() + 4);
            self.fIn.write(msghead.pack());
            self.UnlockIn();
            self.CloseIn();

        return 0;

    def LoadMsgText(self, msghead):
        if (not self.OpenContent(write = False)):
            return None
        self.fContent.seek(msghead.pos);
        msglen = msghead.len;
        if (msglen >= Config.MAX_MSG_SIZE):
            msglen = Config.MAX_MSG_SIZE - 1;
        msg = self.fContent.read(msglen);
        self.CloseContent();
        return msg

    def SendMsg(self, userinfo, msg, mode):
        return None

    def GetMsgCount(self, all):
        path = ""
        if (all):
            path = User.OwnFile(self.name, "msgindex")
        else:
            path = User.OwnFile(self.name, "msgindex2")

        size = Util.GetSize(path)

        if (size <= 0): return 0
        return (size - 4) / MsgHead.size()







