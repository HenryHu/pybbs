from Log import Log
from User import User
from Util import Util
from BCache import BCache
import BoardManager
import Config
import os
import mmap
import struct
import gzip
# BRC!

BRC_CACHE_NUM = 20
BRC_MAXNUM = 50
BRC_ITEMSIZE = BRC_MAXNUM * 4
BRC_FILESIZE = BRC_ITEMSIZE * Config.MAXBOARD

class BrcCacheEntry:
    parser = struct.Struct('=i%dsi' % (BRC_MAXNUM * 4))
    parser_bid = struct.Struct('=i')
    parser_changed = struct.Struct('=i')
    parser_list = struct.Struct('=%ds' % (BRC_MAXNUM * 4))
    _fields = ['_bid', ['_list', 2, '=%dI' % BRC_MAXNUM], '_changed']
    _changed = 0
    _bid = 0
    _list = []
    _index = 0
    _parent = None
    def __init__(self, parent, index):
        self._parent = parent
        self._index = index

    @staticmethod
    def Size():
        return BRC_ITEMSIZE + 8

    def Update(self, full = True):
        if (full):
            self.Load(self._parent._cache_map[BrcCacheEntry.Size() * self._index:BrcCacheEntry.Size() * (self._index+1)])
        else:
            sbid = self._parent._cache_map[BrcCacheEntry.Size() * self._index:BrcCacheEntry.Size() * self._index + 4]
            Util.UnpackX(self, self.parser_bid.unpack(sbid), ['_bid'])
            schanged = self._parent._cache_map[BrcCacheEntry.Size() * (self._index + 1) - 4:BrcCacheEntry.Size() * (self._index + 1)]
            Util.UnpackX(self, self.parser_changed.unpack(schanged), ['_changed'])

    def Commit(self):
        self._parent._cache_map[BrcCacheEntry.Size() * self._index:BrcCacheEntry.Size() * (self._index+1)] = self.Save()

    def Load(self, src):
        Util.Unpack(self, self.parser.unpack(src))
        self._list = list(self._list)

    def Save(self):
        return self.parser.pack(*Util.Pack(self))

    def LoadList(self, src):
        Util.UnpackX(self, self.parser_list.unpack(src), [['_list', 2, '=%dI' % BRC_MAXNUM]])
        self._list = list(self._list)

    def SaveList(self):
        ret = self.parser_list.pack(*Util.PackX(self, [['_list', 2, '=%dI' % BRC_MAXNUM]]))
        return ret

    def Clear(self):
        self._list = [0] * BRC_MAXNUM

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
        brcpath = User.OwnFile(self._userid, ".boardrc.gz")
        changed = -1
        for i in range(0, BRC_CACHE_NUM):
            if (self._cache[i]._changed == 1):
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
            self._cache[i].Update(False)
            if (self._cache[i]._changed == 1):
                self._cache[i].Update(True)
#                Log.debug("entry %d board %d changed, updating" % (i, self._cache[i]._bid))
                data = data[:(self._cache[i]._bid - 1) * BRC_ITEMSIZE] + self._cache[i].SaveList() + data[self._cache[i]._bid * BRC_ITEMSIZE:]
#                data = list(data)
#                data[(self._cache[i]._bid - 1) * BRC_ITEMSIZE:self._cache[i]._bid * BRC_ITEMSIZE] = self._cache[i].Save()
#                data = ''.join(data)
        fbrc.write(data)
        fbrc.close()

    def GetCache(self):
#        Log.debug("GetCache()")
        unchanged = -1
        for i in range(0, BRC_CACHE_NUM):
            self._cache[i].Update(False)
            if self._cache[i]._bid == 0:
#                Log.debug("\tsucc(empty) %d" % i)
                return i
            if self._cache[i]._changed == 0:
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
            self._cache[self._bidcache[board.index]].Update(False)
            if (self._cache[self._bidcache[board.index]]._bid == board.index):
#                Log.debug("Board in brc cache, bidcache ok")
                return self._bidcache[board.index]
        if (entry == -1):
            for i in range(0, BRC_CACHE_NUM):
                self._cache[i].Update(False)
#                Log.debug("bid: %d" % self._cache[i]._bid)
                if (self._cache[i]._bid == board.index):
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
            Log.warn("cannot find cache entry for unread? %s", boardname)
            return False
        self._cache[entry].Update(True)
        for j in range(0, BRC_MAXNUM):
            cur = self._cache[entry]._list[j]
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

    def MarkRead(self, index, board):
        board = BoardManager.BoardManager.GetBoard(board)
        if (board == None):
            return False

        entry = self.FindCacheEntry(board)
        if (entry == -1):
            return True
        centry = self._cache[entry]
        centry.Update(True)
        noentry = False
        for i in range(0, BRC_MAXNUM):
            cur = centry._list[i]
            if (cur == 0):
                if (i == 0):
                    noentry = True
                break
            if (index == cur):
                return True
            elif (index > cur):
                for j in range(BRC_MAXNUM - 1, i, -1):
                    centry._list[j] = centry._list[j-1]
                centry._list[i] = index
                centry._changed = 1
                centry.Commit()
                return True

        if (noentry):
            centry._list[0] = index
            centry._list[1] = 1
            centry._list[2] = 0
            centry._changed = 1
            centry.Commit()
        return True

    def FreeCache(self):
        if _cache_map != None:
            _cache_map.close()
        return

    def Init(self):
        if self._cache_map == None:
            cachepath = User.CacheFile(self._userid, '')
            try:
                os.mkdir(cachepath, 0700)
            except:
                pass
            entrypath = User.CacheFile(self._userid, 'entry')
            try:
                os.stat(entrypath)
            except:
#                Log.debug("no brc cache file for %s, creating" % self._userid)
                brc = '\0' * BRC_CACHE_NUM * BrcCacheEntry.Size()
                fbrc = os.open(entrypath, os.O_RDWR | os.O_CREAT, 0600)
                os.write(fbrc, brc)
                os.close(fbrc)
            fbrc = open(entrypath, "r+b")
            if (fbrc == None):
                Log.error("cannot init brc cache for %s" % self._userid)
                return False
            self._cache_map = mmap.mmap(fbrc.fileno(), BRC_CACHE_NUM * BrcCacheEntry.Size(), prot = mmap.PROT_READ | mmap.PROT_WRITE, flags = mmap.MAP_SHARED)
            fbrc.close()
            if (self._cache_map == None):
                Log.error("failed to mmap cache file for %s" % self.userid)
                return False

            self._cache = [0] * BRC_CACHE_NUM
            for i in range(0, BRC_CACHE_NUM):
                self._cache[i] = BrcCacheEntry(self, i)
                self._cache[i].Load(self._cache_map[BrcCacheEntry.Size() * i:BrcCacheEntry.Size() * (i+1)])

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
        brcpath = User.OwnFile(self._userid, ".boardrc.gz")
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
        self._cache[entry].LoadList(board_read)
        self._cache[entry]._changed = 0
        self._cache[entry]._bid = bindex
        self._cache[entry].Commit()
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
        bh = BCache.GetBoardHeader(boardname)
        self._cache[entry]._list[0] = bh.nowid
        self._cache[entry]._list[1] = 0
        self._cache[entry]._changed = 1
        self._cache[entry].Commit()
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
        while (n < BRC_MAXNUM and self._cache[entry]._list[n] != 0):
            if (index >= self._cache[entry]._list[n]):
                break
            n = n + 1
        if (n < BRC_MAXNUM and (self._cache[entry]._list[n] != 0 or n == 0)):
            self._cache[entry]._list[n] = index
            if (n+1 < BRC_MAXNUM):
                self._cache[entry]._list[n+1] = 0
            self._cache[entry]._changed = 1
            self._cache[entry].Commit()
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


