import json

import Config
import User
from Util import Util
from BoardManager import BoardManager
from UserManager import UserManager
from BCache import BCache
from errors import *

TYPE_BOARD = 1
TYPE_DIR = 2

DEFAULT_LIST_FAVBOARD_COUNT = 20

class FavBoard:
    def __init__(self, index = -1, name = '', father = -1):
        self._index = index
        self._type = type
        self._name = name
        self._father = father
        if (index == -1):
            self._type = TYPE_DIR
        else:
            self._type = TYPE_BOARD

    def IsBoard(self):
        return (self._type == TYPE_BOARD)

    def IsDir(self):
        return (self._type == TYPE_DIR)

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None):
            raise Unauthorized("login first")
        if (action == "list"):
            FavBoardMgr.ListFavBoards(svc, session, params)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def POST(svc, session, params, action):
        if (session == None):
            raise NoPerm("login first")
        raise WrongArgs("unknown action")

    def GetInfo(self, index, user):
        rfb = {}
        rfb['index'] = index
        rfb['father'] = self._father
        if (self.IsBoard()):
            rfb['type'] = 'board'
            board = BoardManager.GetBoardByIndex(self._index + 1)
            if (board != None):
                rfb['binfo'] = board.GetInfoWithUser(user)
        else:
            rfb['type'] = 'dir'
            rfb['name'] = self._name
        return rfb

    def GetInfoJSON(self, index, user):
        return json.dumps(self.GetInfo(index, user))
    
class FavBoardMgr:
    _favboards_set = {}
    @staticmethod
    def LoadFavBoards(userid):
        if (userid not in FavBoardMgr._favboards_set):
            fboards = FavBoardMgr.LoadNewFavBoards(userid)
            if (fboards == None):
                return None
            FavBoardMgr._favboards_set[userid] = fboards
        return FavBoardMgr._favboards_set[userid]

    @staticmethod
    def LoadNewFavBoards(userid):
        fboards = FavBoards(userid)
        fboards.LoadFavBoards()
        return fboards

    @staticmethod
    def ListFavBoards(svc, session, params):
        start = Util.GetInt(params, 'start')
        end = Util.GetInt(params, 'end')
        count = Util.GetInt(params, 'count')
        father = Util.GetInt(params, 'father', -1)

        fboards = FavBoardMgr.LoadFavBoards(session.GetUser().name)
        if (fboards == None):
            raise ServerError("failed to load fav boards")

        fboards.LoadFavBoards()

        start, end = Util.CheckRange(start, end, count, DEFAULT_LIST_FAVBOARD_COUNT, fboards._count)
        if ((start <= end) and (start >= 1) and (end <= fboards._count)):
            first = True
            result = '[\n'
            for index in range(0, fboards._count):
                fboard = fboards._favboards[index]
                if (fboard._father == father):
                    if (not first):
                        result += ',\n'
                    first = False
                    result += fboard.GetInfoJSON(index, session.GetUser())
            result += '\n]'
            svc.writedata(result)
            return
        else:
            raise WrongArgs('invalid arguments')

class FavBoards:
    def __init__(self, userid):
        self._userid = userid
        self._favboards = {}

    def DelFavBoard(self, index):
        if (index >= self._count):
            return self._count
        if (index < 0):
            return self._count

        fboard = self._favboards[index]
        if (fboard.IsDir()):
            j = 0
            while (j < self._count):
                if (self._favboards[j]._father == index):
                    self.DelFavBoard(j)
                    if (j < index):
                        index = index - 1
                    j = j - 1
                j = j + 1
        self._count = self._count - 1
        j = index
        while (j < self._count):
            self._favboards[j] = self._favboards[j+1]
            j = j + 1
        j = 0
        while (j < self._count):
            if (self._favboards[j]._father >= index):
                self._favboards[j]._father = self._favboards[j]._father-1
            j = j + 1
        if (self._current >= index):
            self._current = self._current - 1
        if (self._count == 0):
            self._count = 1
            self._favboards[0] = FavBoard(0)
        return 0

    def LoadFavBoards(self):
        path = User.User.OwnFile(self._userid, "favboard")
        self._current = -1
        fd = open(path, "rb")
        if (fd != None):
            magic = Util.ReadInt(fd)
            if (magic != 0x8080):
                self._count = magic
                index = 0
                while (index < self._count):
                    bindex = Util.ReadInt(fd)
                    self._favboards[index] = FavBoard(bindex)
                    index = index + 1
            else:
                self._count = Util.ReadInt(fd)
                index = 0
                while (index < self._count):
                    flag = Util.ReadInt(fd)
                    title = ''
                    if (flag == -1):
                        len = Util.ReadChar(fd)
                        title = Util.gbkDec(Util.CString(fd.read(len)))
                    father = Util.ReadInt(fd)
                    self._favboards[index] = FavBoard(flag, title, father)
                    index = index + 1
            fd.close()
        if (self._count <= 0):
            fd = open(Config.BBS_ROOT + "etc/initial_favboard", "r")
            if (fd == None):
                self._count = 1
                self._favboards[0] = FavBoard(0)
            else:
                self._count = 1
                self._favboards[0] = FavBoard(0)
                while (1):
                    board = Util.ReadString(fd)
                    if (board == ''):
                        break
                    bobj = BoardManager.GetBoard(board)
                    if (bobj != None):
                        self._favboards[self._count] = FavBoard(bobj.index - 1)
                fd.close()
        else:
            count = self._count
            index = 0
            while (index < self._count):
                fboard = self._favboards[index]
                if (fboard.IsDir()):
                    index = index + 1
                    continue
                bindex = fboard._index
                board = BoardManager.GetBoardByIndex(bindex + 1)
                user = UserManager.LoadUser(self._userid)
                if ((bindex >= 0) and (bindex <= BCache.GetBoardCount())
                        and (user != None)
                        and (board != None)
                        and (board.CheckSeePerm(user))):
                    index = index + 1
                    continue
                self.DelFavBoard(index)
                index = index + 1
            if (count != self._count):
                self.SaveFavBoards()

    def SaveFavBoards(self):
        pass

