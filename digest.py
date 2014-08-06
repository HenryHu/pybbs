import re
import os
import stat
import json
import struct
import time
import Config
import Board
import Post
import BoardManager
from Util import Util
from Log import Log
from errors import *

DEFAULT_DIGEST_LIST_COUNT = 20

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

    def GetModTime(self):
        try:
            st = os.stat(self.realpath())
            mtime = st.st_mtime
        except:
            mtime = time.time()
        return mtime

    def names_path(self):
        return "%s/.Names" % self.realpath()

    def realpath(self):
        return "%s/%s" % (Config.BBS_ROOT, self.path())

    def path(self):
        if (self.fname):
            return "%s/%s" % (self.basepath, self.fname)
        else:
            return self.basepath

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
                    elif (item.title.find("(BM: SYSOPS)") != -1):
                        sysop_only += 1
                    elif (item.title.find("(BM: ZIXIAs)") != -1):
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

        if (len(route) == 0):
            return self
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

    def GetRange(self, user, route, start, end, has_perm = False, need_perm = False):
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
        if (not parent.IsDir()):
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
        info['attach'] = self.attachpos
        if (self.host != ''):
            info['host'] = self.host
            info['port'] = self.port
            info['type'] = 'link'
        elif (self.IsDir()):
            info['type'] = 'dir'
        elif (self.IsFile()):
            info['type'] = 'file'
        else:
            info['type'] = 'other'
        info['mtime'] = int(self.GetModTime())
        return info

    def GetInfoForUser(self, user):
        info = self.GetInfo()
        info['id'] = self.EffectiveId(user) + 1
        return info

    def GetAttachLink(self, session):
        _hash = Util.HashGen(self.path(), "python nb")
        filename = ''
        for i in range(2):
            filename += "%0x" % struct.unpack('=I', _hash[i*4:(i+1)*4])
        link = "http://%s/bbscon.php?b=xattach&f=%s" % (session.GetMirror(Config.Config.GetInt('ATTACHMENT_PORT', 80)), filename)

        linkfile = "%s/boards/xattach/%s" % (Config.BBS_ROOT, filename)
        target = "../../%s" % self.path()
        try:
            os.symlink(target, linkfile)
        except:
            # we should not omit other errors
            # anyway...
            pass
        return link

class Digest:
    root = DigestItem("0Announce")
    def __init__(self, board, path):
        self.board = board
        self.path = path
        self.root = DigestItem(self.path)

    @staticmethod
    def GET(svc, session, params, action):
        if (session is None): raise Unauthorized('login first')
        if not session.CheckScope('bbs'): raise NoPerm("out of scope")
        user = session.GetUser()
        boardname = svc.get_str(params, 'board', '')
        if (boardname):
            board = BoardManager.BoardManager.GetBoard(boardname)
            if (board is None): raise NotFound('board %s not found' % boardname)
            if (not board.CheckReadPerm(user)):
                raise NoPerm('permission denied')
            basenode = board.digest.root
            has_perm = user.IsDigestMgr() or user.IsSysop() or user.IsSuperBM()
        else:
            basenode = Digest.root
            has_perm = user.IsDigestMgr()

        if (action == "list"):
            route = svc.get_str(params, 'route')
            start = svc.get_int(params, 'start', 1)
            end = svc.get_int(params, 'end', start + DEFAULT_DIGEST_LIST_COUNT - 1)
            Digest.List(svc, basenode, route, start, end, session, has_perm)
            return
        elif (action == "view"):
            route = svc.get_str(params, 'route')
            start = svc.get_int(params, 'start', 0)
            count = svc.get_int(params, 'count', 0)
            Digest.View(svc, basenode, route, session, has_perm, start, count)
            return
        else:
            raise WrongArgs('unknown action %s' % action)

    @staticmethod
    def ParseRoute(route):
        ret = []
        items = re.split('-', route)
        # first item: 'x'
        items = items[1:]
        for item in items:
            try:
                ret += [int(item)]
            except:
                raise WrongArgs('fail to parse route element: %s' % item)
        return ret

    @staticmethod
    def List(svc, basenode, route, start, end, session, has_perm):
        route_array = Digest.ParseRoute(route)
        parent = basenode.GetItem(session.GetUser(), route_array, has_perm)
        if (not parent):
            raise WrongArgs('route %s does not exist!' % route)
        if (not parent.IsDir()):
            raise WrongArgs('route %s does not point to a dir!' % route)
        items = basenode.GetRange(session.GetUser(), route_array, start, end, has_perm)
        result = {}
        result['parent'] = parent.GetInfoForUser(session.GetUser())
        result['count'] = len(items)
        result_list = []
        for item in items:
            result_list += [item.GetInfoForUser(session.GetUser())]
        result['items'] = result_list

        svc.writedata(json.dumps(result))

    @staticmethod
    def View(svc, basenode, route, session, has_perm, start, count):
        route_array = Digest.ParseRoute(route)
        item = basenode.GetItem(session.GetUser(), route_array, has_perm)
        if (not item):
            raise WrongArgs('route %s does not exist!' % route)
        if (not item.IsFile()):
            raise WrongArgs('route %s does not point to a file' % route)
        result = {}
        result['item'] = item.GetInfoForUser(session.GetUser())
        postinfo = Post.Post(item.realpath(), None)
        (result['content'], result['has_end']) = postinfo.GetContent(start, count)
        attachlist = postinfo.GetAttachListByType()
        result['picattach'] = attachlist[0]
        result['otherattach'] = attachlist[1]
        if (attachlist[0] or attachlist[1]):
            result['attachlink'] = item.GetAttachLink(session)
        svc.writedata(json.dumps(result))


