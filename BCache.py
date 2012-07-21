#!/usr/bin/env python

import Config
import struct
import mmap
import os
import fcntl
import Board
from Util import Util
from Log import Log
from sysv_ipc import *
from cstruct import *
from errors import *

@init_fields
class BoardHeader(object):
    '''struct boardheader'''

    _fields = [
            ['filename', Str(Config.STRLEN)],
            ['BM', Str(Config.BM_LEN)],
            ['title', Str(Config.STRLEN)],
            ['level', U32()],
            ['nowid', U32()],
            ['clubnum', U32()],
            ['flag', U32()],
            ['adv_club', U32()],
            ['createtime', U32()],
            ['toptitle', I32()],
            ['ann_path', Str(128)],
            ['group', I32()],
            ['title_level', I8()],
            ['des', Str(195)]
    ]

    def read(self, pos, len):
        return BCache.bcache[self.idx * self.size + pos:self.idx * self.size + pos + len]

    def write(self, pos, data):
        BCache.bcache[self.idx * self.size + pos : self.idx * self.size + pos + len(data)] = data

    def __init__(self, idx):
        self.idx = idx - 1 # we start from 0 here...

@init_fields
class BoardStatus(object):
    '''struct boardheader'''
    _fields = [
            ['total', I32()],
            ['lastpost', I32()],
            ['updatemark', I32()],
            ['updatetitle', I32()],
            ['updateorigin', I32()],
            ['currentusers', I32()]
    ]


    def read(self, pos, len):
        return BCache.brdshm.read(len, 4 + self.size * self.idx + pos)

    def write(self, pos, data):
        BCache.brdshm.write(data, 4 + self.size * self.idx + pos)

    def __init__(self, idx):
        self.idx = idx - 1 # we start from 0 here...

class BCache:
    bcache = None
    brdshm = None
    BRDSHM_SIZE = 4 + Config.MAXBOARD * BoardStatus.size

    @staticmethod
    def GetBoardCount():
        if (BCache.brdshm == None):
            BCache.Init()
        return struct.unpack('=i', BCache.brdshm.read(4, 0))[0]

    @staticmethod
    def SetBoardCount(count):
        if (BCache.brdshm == None):
            BCache.Init()
        BCache.brdshm.write(struct.pack('=i', count), 0)

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
        Log.info("Initializing BCache")
        if (BCache.bcache == None):
            boardf = open(Config.Config.GetBoardsFile(), 'r+b')
            if (boardf == None):
                Log.error("Cannot open boards file")
                raise ServerError("fail to open boards file")
            try:
                BCache.bcache = mmap.mmap(boardf.fileno(), Config.MAXBOARD * BoardHeader.size, flags = mmap.MAP_SHARED, prot = mmap.PROT_READ)
                if (BCache.bcache == None):
                    Log.error("Cannot mmap boards file")
                    raise ServerError("fail to mmap boards file")
            finally:
                boardf.close()
        Log.info("Got boards list")

        if (BCache.brdshm == None):
            try:
                Log.info("Attaching to BCache shared memory")
                BCache.brdshm = SharedMemory(Config.Config.GetInt("BCACHE_SHMKEY", 3693), size = BCache.BRDSHM_SIZE)
#                print "Got SHM"
#                for i in range(0, Config.MAXBOARD):
#                    bh = BoardHeader(i)
#                    if (bh.filename != ''):
#                        bs = BoardStatus(i)
#                        print "Board: ", bh.filename, " lastpost: ", bs.lastpost, " total: ", bs.total, " curruser: ", bs.currentusers
#                print BoardStatus.size
            except:
                # do initialization
                Log.info("Creating BCache shared memory")
                BCache.brdshm = SharedMemory(Config.Config.GetInt("BCACHE_SHMKEY", 3693), size = BCache.BRDSHM_SIZE, flags = IPC_CREAT, mode = 0660)
                fd = BCache.Lock()
                try:
                    maxbrd = -1
                    for i in range(0, Config.MAXBOARD):
                        bh = BoardHeader(i)
                        if (bh.filename != ''):
                            bs = BoardStatus(i)
                            board = Board(bh, bs, i)
                            board.UpdateLastPost()
                            maxbrd = i

                    if (maxbrd != -1):
                        BCache.SetBoardCount(maxbrd + 1)
                finally:
                    BCache.Unlock(fd)

        Log.info("BCache initialized")

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
            BCache.bcache = mmap.mmap(boardf.fileno(), Config.MAXBOARD * BoardHeader.size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ)
        else:
            BCache.bcache = mmap.mmap(boardf.fileno(), Config.MAXBOARD * BoardHeader.size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ | mmap.PROT_WRITE)
        boardf.close()
        return True

    @staticmethod
    def Lock():
        lockfd = os.open(Config.BBS_ROOT + "bcache.lock", os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0600)
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
        os.close(lockfd)
    
    @staticmethod
    def GetNextID(boardname):
        ret = -1
        lockfd = BCache.Lock()
        if (lockfd < 0):
            Log.warn("BCache lock fail")
            return -1

        try:
            bh = BCache.GetBoardHeader(boardname)
            if (bh != None):
                bh.nowid += 1
                ret = bh.nowid
            else:
                Log.warn("GetNextID() fail for board %s" % boardname)
        finally:
            BCache.Unlock(lockfd)
        return ret

