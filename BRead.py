from Log import Log
from Util import Util
import BCache
import BoardManager
import Config
import User
from cstruct import *

import os
import mmap
import struct
import gzip

# BRC!

BRC_CACHE_NUM = 20
BRC_MAXNUM = 50
BRC_ITEMSIZE = BRC_MAXNUM * 4
BRC_FILESIZE = BRC_ITEMSIZE * Config.MAXBOARD

@init_fields
class BrcCacheEntry(object):
    _fields = [
        ['bid', I32()],
        ['list', Array(U32, BRC_MAXNUM)],
        ['changed', I32()]
    ]
    _index = 0
    _parent = None
    def __init__(self, parent, index):
        self._parent = parent
        self._index = index

    def read(self, pos, len):
        start = self.size * self._index + pos
#        Log.debug("reading %d + %d" % (pos, len))
#        Log.debug("ret: %r" % self._parent._cache_map[start : start + len])
        return self._parent._cache_map[start : start + len]

    def write(self, pos, data):
        start = self.size * self._index + pos
        self._parent._cache_map[start : start + len(data)] = data

    def get_list(self):
        return self.read(BrcCacheEntry.list._base, BrcCacheEntry.list.size)

    def put_list(self, data):
        assert len(data) == BrcCacheEntry.list.size
        self.write(BrcCacheEntry.list._base, data)

    def Clear(self):
        for i in xrange(BRC_MAXNUM):
            self.list[i] = 0

class BRead:
    _userid = ''
    _bidcache = {}
    def __init__(self, userid):
        self._userid = userid
        self._cache_map = None
        self._cache = []

    def Update(self):
#        Log.debug("Update()")
        if (self._cache_map == None):
            return
        brcpath = User.User.OwnFile(self._userid, ".boardrc.gz")
        changed = -1
        for i in range(0, BRC_CACHE_NUM):
            if (self._cache[i].changed == 1):
                changed = i
                break
        if (changed == -1):
            return
        fbrc = gzip.open(brcpath, "rb", 6)
        data = '\0' * BRC_FILESIZE
        if (fbrc == None):
            os.remove(brcpath)
        else:
            data = fbrc.read(BRC_FILESIZE)
            fbrc.close()
        fbrc = gzip.open(brcpath, "wb", 6)
        if (fbrc == None):
            os.remove(brcpath)
            return
        for i in range(0, BRC_CACHE_NUM):
            if (self._cache[i].changed == 1):
                self._cache[i].changed = 0
#                Log.debug("entry %d board %d changed, updating" % (i, self._cache[i]._bid))
                data = data[:(self._cache[i].bid - 1) * BRC_ITEMSIZE] + self._cache[i].get_list() + data[self._cache[i].bid * BRC_ITEMSIZE:]
#                data = list(data)
#                data[(self._cache[i]._bid - 1) * BRC_ITEMSIZE:self._cache[i]._bid * BRC_ITEMSIZE] = self._cache[i].Save()
#                data = ''.join(data)
        fbrc.write(data)
        fbrc.close()

    def GetCache(self):
#        Log.debug("GetCache()")
        unchanged = -1
        for i in range(0, BRC_CACHE_NUM):
            if self._cache[i].bid == 0:
#                Log.debug("\tsucc(empty) %d" % i)
                return i
            if self._cache[i].changed == 0:
                unchanged = i
        if (unchanged != -1):
#            Log.debug("\tsucc(unchanged) %d oldbid %d" % (unchanged, self._cache[unchanged]._bid))
            return unchanged
        self.Update()
#        Log.debug("\tfail, flushed all")
        return 0

    def FindCacheEntry(self, board):
        entry = -1
        if (board.index in self._bidcache):
            if (self._cache[self._bidcache[board.index]].bid == board.index):
#                Log.debug("Board in brc cache, bidcache ok")
                return self._bidcache[board.index]
        if (entry == -1):
            for i in range(0, BRC_CACHE_NUM):
#                Log.debug("bid: %d" % self._cache[i].bid)
                if (self._cache[i].bid == board.index):
#                    Log.debug("Board in brc cache, bidcache old")
                    entry = i
                    break
        if (entry == -1):
#            Log.debug("Board %d not in brc cache" % board.index)
            return entry
        self._bidcache[board.index] = entry
        return entry

    def QueryUnread(self,index, boardname):
#        Log.debug("QueryUnread: %s %d" % (boardname, index))
        board = BoardManager.BoardManager.GetBoard(boardname)
        if (board == None):
            Log.error("Fail to load board %s for unread?" % boardname)
            return False
        entry = self.FindCacheEntry(board)
        if (entry == -1):
            Log.warn("cannot find cache entry for unread? %s" % boardname)
            return False
        for j in range(0, BRC_MAXNUM):
            cur = self._cache[entry].list[j]
#            Log.debug("read: %d" % cur)
            if (cur == 0):
                if (j == 0):
#                    Log.debug("empty bread cache")
                    return True
#                Log.debug("reach bread cache end")
                return False
            if (index > cur):
#                Log.debug("not found")
                return True
            elif (index == cur):
#                Log.debug("found")
                return False
        return False

    def MarkRead(self, index, boardname):
        board = BoardManager.BoardManager.GetBoard(boardname)
        if (board == None):
            return False

        entry = self.FindCacheEntry(board)
        if (entry == -1):
            return True
        centry = self._cache[entry]
        noentry = False
        for i in range(0, BRC_MAXNUM):
            cur = centry.list[i]
            if (cur == 0):
                if (i == 0):
                    noentry = True
                break
            if (index == cur):
                return True
            elif (index > cur):
                for j in range(BRC_MAXNUM - 1, i, -1):
                    centry.list[j] = centry.list[j-1]
                centry.list[i] = index
                centry.changed = 1
                return True

        if (noentry):
            centry.list[0] = index
            centry.list[1] = 1
            centry.list[2] = 0
            centry._changed = 1
        return True

    def FreeCache(self):
        if self._cache_map != None:
            self._cache_map.close()
        return

    def Init(self):
        if self._cache_map == None:
            cachepath = User.User.CacheFile(self._userid, '')
            try:
                os.mkdir(cachepath, 0700)
            except:
                pass
            entrypath = User.User.CacheFile(self._userid, 'entry')
            try:
                os.stat(entrypath)
            except:
#                Log.debug("no brc cache file for %s, creating" % self._userid)
                brc = '\0' * BRC_CACHE_NUM * BrcCacheEntry.size
                fbrc = os.open(entrypath, os.O_RDWR | os.O_CREAT, 0600)
                os.write(fbrc, brc)
                os.close(fbrc)
            fbrc = open(entrypath, "r+b")
            if (fbrc == None):
                Log.error("cannot init brc cache for %s" % self._userid)
                return False
            self._cache_map = mmap.mmap(fbrc.fileno(), BRC_CACHE_NUM * BrcCacheEntry.size, prot = mmap.PROT_READ | mmap.PROT_WRITE, flags = mmap.MAP_SHARED)
            fbrc.close()
            if (self._cache_map == None):
                Log.error("failed to mmap cache file for %s" % self._userid)
                return False

            self._cache = [0] * BRC_CACHE_NUM
            for i in range(0, BRC_CACHE_NUM):
                self._cache[i] = BrcCacheEntry(self, i)

        return True

    def Load(self, boardname):
        board = BoardManager.BoardManager.GetBoard(boardname)
        if (board == None):
            Log.error("cannot found board %s" % boardname)
            return False
        bindex = board.index
        self.Init()
        if (self._cache_map == None):
            return False
        entry = self.FindCacheEntry(board)
        if (entry != -1):
#            Log.debug("Load: already in cache")
            return True
        brcpath = User.User.OwnFile(self._userid, ".boardrc.gz")
        try:
            fbrc = gzip.open(brcpath, "rb", 6)
        except:
            fbrc = None
        if (fbrc == None):
            fbrc = gzip.GzipFile(brcpath, "wb", 6)
            if (fbrc == None):
                Log.error("failed to open board read cache for %s" % self._userid)
                return False
            Log.warn("recreating brc %d" % BRC_FILESIZE)
            fbrc.write('\0' * BRC_FILESIZE)
            fbrc.close()
            fbrc = gzip.open(brcpath, "rb", 6)
            if (fbrc == None):
                Log.error("failed to open board read cache for %s" % self._userid)
                return False
        entry = self.GetCache()
        self._cache[entry].Clear()
#        Log.debug("Load board no.: %d" % bindex)
        fbrc.seek((bindex - 1) * BRC_ITEMSIZE);
        board_read = fbrc.read(BRC_ITEMSIZE)
#        Log.debug("got list: %r" % board_read)
        self._cache[entry].put_list(board_read)
        self._cache[entry].changed = 0
        self._cache[entry].bid = bindex
        fbrc.close()
        return True

    def Clear(self, boardname):
        board = BoardManager.BoardManager.GetBoard(boardname)
        if (board == None):
            Log.error("Fail to load board %s for clear" % boardname)
            return False
        entry = self.FindCacheEntry(board)
        if (entry == -1):
            return False
        bh = BCache.BCache.GetBoardHeader(boardname)
        if bh is None:
            Log.error("Fail to load boardheader for %s" % boardname)
            return False
        self._cache[entry].list[0] = bh.nowid
        self._cache[entry].list[1] = 0
        self._cache[entry].changed = 1
        return True

    def ClearTo(self, index, boardname):
        board = BoardManager.BoardManager.GetBoard(boardname)
        if (board == None):
            Log.error("Fail to load board %s for clear_to" % boardname)
            return False
        entry = self.FindCacheEntry(board)
        if (entry == -1):
            return False
        n = 0
        while (n < BRC_MAXNUM and self._cache[entry].list[n] != 0):
            if (index >= self._cache[entry].list[n]):
                break
            n = n + 1
        if (n < BRC_MAXNUM and (self._cache[entry].list[n] != 0 or n == 0)):
            self._cache[entry].list[n] = index
            if (n+1 < BRC_MAXNUM):
                self._cache[entry].list[n+1] = 0
            self._cache[entry].changed = 1
        return True

class BReadMgr:
    _breads = {}

    @staticmethod
    def LoadBRead(userid):
        if (userid not in BReadMgr._breads):
            bread = BReadMgr.LoadNewBRead(userid)
            if (bread == None):
                return None
            BReadMgr._breads[userid] = bread
        return BReadMgr._breads[userid]

    @staticmethod
    def LoadNewBRead(userid):
        bread = BRead(userid)
        bread.Init()
        return bread


