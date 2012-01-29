#!/usr/bin/env python

import Config
import struct
import mmap
from Util import Util
from sysv_ipc import *

class BoardHeader:
    parser = struct.Struct('=%ds%ds%dsIIIIIli128sic195s' % (Config.STRLEN, Config.BM_LEN, Config.STRLEN))
    _fields = [['filename', 1], ['BM', 1], ['title', 1], 'level', 'nowid', 'clubnum', 'flag', 'adv_club', 'createtime', 'toptitle', ['ann_path',1], 'group', 'title_level', ['des',1]]

    # struct boardheader
    @staticmethod
    def size():
        return BoardHeader.parser.size

    def unpack(self):
        Util.Unpack(self, BoardHeader.parser.unpack(BCache.bcache[self.idx * BoardHeader.parser.size:(self.idx + 1) * BoardHeader.parser.size]))
        return

    def pack(self):
        BCache.bcache[self.idx * BoardHeader.parser.size:(self.idx + 1) * BoardHeader.parser.size] = BoardHeader.parser.pack(Util.Pack(self))

    def __init__(self, idx):
        self.idx = idx - 1 # we start from 0 here...
        self.unpack()

class BoardStatus:
    parser = struct.Struct('=iiiiii')
    _fields = ['total', 'lastpost', 'updatemark', 'updatetitle', 'updateorigin', 'currentusers']

    # struct boardheader
    @staticmethod
    def size():
        return BoardStatus.parser.size

    def unpack(self):
        Util.Unpack(self, BoardStatus.parser.unpack(BCache.brdshm.read(self.size(), 4 + self.size() * self.idx)))
        return

    def pack(self):
        BCache.brdshm.write(BoardStatus.parser.pack(Util.Pack(self)), 4 + self.size() * self.idx)

    def __init__(self, idx):
        self.idx = idx - 1 # we start from 0 here...
        self.unpack()

class BCache:
    bcache = None
    brdshm = None
    BRDSHM_SIZE = 4 + Config.MAXBOARD * BoardStatus.size()

    @staticmethod
    def GetBoardCount():
        if (BCache.brdshm == None):
            BCache.Init()
        return struct.unpack('=i', BCache.brdshm.read(4, 0))[0]

    @staticmethod
    def GetBoardHeader(name):
        for i in range(0, BCache.GetBoardCount()):
            bh = BoardHeader(i + 1)
            if (bh.filename == name):
                return bh
        return None

    @staticmethod
    def GetBoardNum(name):
        for i in range(0, BCache.GetBoardCount()):
            bh = BoardHeader(i + 1)
            if (bh.filename == name):
                return i + 1
        return 0

    @staticmethod
    def Init():
        if (BCache.bcache == None):
            boardf = open(Config.Config.GetBoardsFile(), 'r+b')
            if (boardf == None):
                print "Cannot open boards file"
                return False
            BCache.bcache = mmap.mmap(boardf.fileno(), Config.MAXBOARD * BoardHeader.size(), flags = mmap.MAP_SHARED, prot = mmap.PROT_READ)
            if (BCache.bcache == None):
                print "Cannot map boards file"
                boardf.close()
                return False
            boardf.close()

        if (BCache.brdshm == None):
            try:
                BCache.brdshm = SharedMemory(Config.Config.GetInt("BCACHE_SHMKEY", 3693), size = BCache.BRDSHM_SIZE)
#                print "Got SHM"
#                for i in range(0, Config.MAXBOARD):
#                    bh = BoardHeader(i)
#                    if (bh.filename != ''):
#                        bs = BoardStatus(i)
#                        print "Board: ", bh.filename, " lastpost: ", bs.lastpost, " total: ", bs.total, " curruser: ", bs.currentusers
#                print BoardStatus.size()
            except:
                # do initialization
                print "Init SHM"
                BCache.brdshm = SharedMemory(Config.Config.GetInt("BCACHE_SHMKEY", 3693), size = BCache.BRDSHM_SIZE, flags = IPC_CREAT)
                fd = BCache.Lock()
                for i in range(0, Config.MAXBOARD):
                    bh = BoardHeader(i)
                    if (bh.filename != ''):
                        bs = BoardStatus(i)
                        # TODO
                fd = BCache.Unlock()

        return

    @staticmethod
    def SetReadOnly(readonly):
        if (BCache.bcache != None):
            BCache.bcache.close()
        boardf = open(Config.Config.GetBoardsFile(), 'r+b')
        if (boardf == None):
            print "Cannot open boards file"
            return False
        if (readonly):
            BCache.bcache = mmap.mmap(boardf.fileno(), Config.MAXBOARD * BoardHeader.size(), flags=mmap.MAP_SHARED, prot=mmap.PROT_READ)
        else:
            BCache.bcache = mmap.mmap(boardf.fileno(), Config.MAXBOARD * BoardHeader.size(), flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
        boardf.close()
        return True

    @staticmethod
    def Lock():
        lockfd = os.open("bcache.lock", os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0600)
        if (lockfd == None):
            Log.warn("fail to create bcache.lock")
            return None
        BCache.SetReadOnly(False)
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        return lockfd

    @staticmethod
    def Unlock(lockfd):
        fcntl.flock(lockfd, fcntl.LOCK_UN)
        BCache.SetReadOnly(True)
        lockfd.close()
    
    @staticmethod
    def GetNextID(boardname):
        ret = -1
        lockfd = BCache.Lock()
        if (lockfd == None):
            Log.warn("BCache lock fail")
            return -1

        bh = BCache.GetBoardHeader(boardname)
        if (bh != None):
            bh.nowid= bh.nowid + 1
            bh.pack()
            ret = bh.nowid
        else:
            Log.warn("GetNextID() fail for board %s" % boardname)
        BCache.Unlock(lockfd)
        return ret
