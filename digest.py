import re
import os
import stat
import time
import Config
import Board
from Util import Util
from Log import Log

class Digest:
    def __init__(self, board, path):
        self.board = board
        self.path = path
        self.root = DigestItem(self.path)

class DigestItem:
    def __init__(self, basepath):
        self.basepath = basepath
        self.title = ''
        self.host = ''
        self.port = 0
        self.attachpos = 0
        self.fname = ''
        self.mtitle = ''
        self.items = []
        self.update_time = 0

        self.id = 0
        self.sysop_only = 0
        self.bms_only = 0
        self.zixia_only = 0

    def IsDir(self):
        try:
            st = os.stat(self.realpath())
            return stat.S_ISDIR(st.st_mode)
        except:
            return False

    def IsFile(self):
        try:
            st = os.stat(self.realpath())
            return stat.S_ISREG(st.st_mode)
        except:
            return False

    def names_path():
        return "%s/.Names" % self.realpath()

    def realpath(self):
        return "%s/%s" % (Config.BBS_ROOT, self.path())

    def path(self):
        return "%s/%s" % (self.basepath, self.fname)

    def CheckUpdate(self):
        try:
            stat = os.stat(self.names_path())
            if (stat.st_mtime > self.update_time):
                self.LoadNames()
        except:
            # what? maybe it's deleted?
            # so we should update the upper layer...
            return False

        return True

    def LoadNames(self):
        try:
            f = open(self.names_path(), "r")
        except IOError:
            return 0

        stat = os.fstat(f.fileno())
        self.update_time = stat.st_mtime

        item = DigestItem(self.path())

        hostname = ''
        _id = 0
        bms_only = 0
        sysop_only = 0
        zixia_only = 0
        while (True):
            line = f.readline()
            if (line == ""): break
            npos = line.find("\n")
            if (npos != -1): line = line[:npos]

            if (line[:1] == '#'):
                if (line[:8] == "# Title="):
                    if (not self.mtitle):
                        self.mtitle = line[8:]
            result = re.match('([^=]*)=(.*)', line)
            if (result):
                key = result.group(1)
                value = result.group(2)
                if (key == "Name"):
                    item.title = value
                    item.attachpos = 0
                elif (key == "Path"):
                    if (value[:2] == "~/"):
                        item.fname = value[2:]
                    else:
                        item.fname = value
                    if (item.fname.find("..") != -1):
                        continue
                    if (item.title.find("(BM: BMS)") != -1):
                        bms_only += 1
                    if (item.title.find("(BM: SYSOPS)") != -1):
                        sysop_only += 1
                    if (item.title.find("(BM: ZIXIAs)") != -1):
                        zixia_only += 1
                    if (item.fname.find("!@#$%") != -1):
                        parts = re.split('[!@#$%]', item.fname)
                        newparts = []
                        for part in parts:
                            if (part):
                                newparts += [part]
                        hostname = newparts[0]
                        item.fname = newparts[1]
                        try:
                            item.port = int(newparts[2])
                        except:
                            item.port = 0
                    item.id = _id
                    _id += 1
                    item.bms_only = bms_only
                    item.sysop_only = sysop_only
                    item.zixia_only = zixia_only
                    item.host = hostname
                    self.items += [item]
                    print "item: ", vars(item), _id
                    item = DigestItem(self.path())
                    hostname = ''
                elif (key == "Host"):
                    hostname = value
                elif (key == "Port"):
                    try:
                        item.port = int(value)
                    except:
                        item.port = 0
                elif (key == "Attach"):
                    try:
                        item.attachpos = int(value)
                    except:
                        item.attachpos = 0

        f.close()
        return 1

    def GetItem(self, user, route, has_perm = False, need_perm = False):
        self.CheckUpdate()

        # for normal items, permission does not matter
        if (self.mtitle.find("(BM:") != -1):
            if (Board.Board.IsBM(user, self.mtitle[4:],) or user.IsSysop()):
                has_perm = True
            elif (need_perm and not has_perm):
                return None
        if (self.mtitle.find("(BM: BMS)") != -1
                or self.mtitle.find("(BM: SECRET)") != -1
                or self.mtitle.find("(BM: SYSOPS)") != -1):
            need_perm = True # take effect at next level...

        target = route[0] - 1
        _id = target
        if (_id >= len(self.items)):
            return None
        while (self.items[_id].EffectiveId(user) < target):
            _id += 1
            if (_id >= len(self.items)):
                return None
        item = self.items[_id]
        # what the ....
        item.mtitle = item.title
        if (len(route) == 1):
            # last level...
            return item
        else:
            if (item.IsDir()):
                if (not item.CheckUpdate()):
                    return None
                return item.GetItem(user, route[1:], has_perm, need_perm)
            else:
                return None

    def GetRange(self, user, route, has_perm, need_perm, start, end):
        self.CheckUpdate()

        # only for permission check
        firstitem = self.GetItem(user, route + [start], has_perm, need_perm)
        if (not firstitem):
            return []
        # range? disabled for partial result
        #lastitem = self.GetItem(user, route + [end], has_perm, need_perm)
        #if (not lastitem):
        #    return None

        parent = self.GetItem(user, route, has_perm, need_perm)
        if (not parent):
            return []

        result = []
        _id = start - 1
        for i in range(start, end + 1):
            target = i - 1
            if (_id >= len(parent.items)):
                return []
            while (parent.items[_id].EffectiveId(user) < target):
                _id += 1
                if (_id >= len(parent.items)):
                    # give partial result instead of error...
                    return result
            item = parent.items[_id]
            # necessary?...
            item.mtitle = item.title
            result += [item]

        return result

    def EffectiveId(self, user):
        _id = self.id
        if (user.IsSysop()):
            return _id
        if (not user.IsSysop()):
            _id -= self.sysop_only
        if (not user.IsBM()):
            _id -= self.bms_only
        if (not user.IsSECANC()):
            _id -= self.zixia_only
        return _id

    def GetInfo(self):
        info = {}
        info['mtitle'] = Util.gbkDec(self.mtitle)
        info['title'] = Util.gbkDec(self.title)
        info['host'] = self.host
        info['port'] = self.port
        info['attach'] = self.attachpos

    def GetInfoForUser(self, user):
        info = self.GetInfo()
        info['id'] = self.EffectiveId(user) + 1

