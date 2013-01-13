from BCache import *
import json
from errors import *
import Board

DEFAULT_LIST_BOARD_COUNT = 20

class BoardManager:
    boards = {}
    s_boards = []
    _iboards = {}
    @staticmethod
    def LoadBoards():
        for i in range(0, BCache.GetBoardCount()):
            bh = BoardHeader(i+1)
            if (bh.filename != ''):
                bs = BoardStatus(i+1)
                board = Board.Board(bh, bs, i+1)
                BoardManager.boards[bh.filename] = board
                BoardManager._iboards[i+1] = board
        BoardManager.s_boards = BoardManager.boards.keys()
        BoardManager.s_boards.sort(key = str.lower)
        return

    @staticmethod
    def GetBoardByIndex(index):
        if ((index > 0) and (index <= BCache.GetBoardCount())):
            return BoardManager._iboards[index]
        else:
            return None

    @staticmethod
    def GetBoard(name):
        if (BoardManager.boards.has_key(name)):
            return BoardManager.boards[name]
        else:
            return None

    @staticmethod
    def GetBoardByParam(svc, params):
        board = svc.get_str(params, 'board')
        bo = BoardManager.GetBoard(board)
        if (bo == None):
            raise NotFound('board not found')
        else:
            return bo

    @staticmethod
    def Init():
        BoardManager.LoadBoards()
        return

    @staticmethod
    def ListBoards(svc, session, params):
        start = Util.GetInt(params, 'start')
        end = Util.GetInt(params, 'end')
        count = Util.GetInt(params, 'count')
        group = Util.GetInt(params, 'group')

        start, end = Util.CheckRange(start, end, count, DEFAULT_LIST_BOARD_COUNT, BCache.GetBoardCount())
        if ((start <= end) and (start >= 1) and (end <= BCache.GetBoardCount())): 
            boards = BoardManager.GetBoards(session, start, end)
            first = True
            result = '[\n'
            for board in boards:
                if group != 0:
                    if board.GetGroup() != group:
                        continue
                if (not first):
                    result += ',\n'
                first = False
                result += board.GetInfoWithUserJSON(session.GetUser())
            result += '\n]'
            svc.writedata(result)
            return
        else:
            raise WrongArgs('invalid arguments')


    @staticmethod
    def GetBoards(session, start, end):
        currcount = 0
        ret = []
        user = session.GetUser()
        for i in range(0, BCache.GetBoardCount()):
            board = BoardManager.boards[BoardManager.s_boards[i]]
            if (board.CheckSeePerm(user)):
                currcount = currcount + 1
                if (currcount >= start):
                    ret.append(board)
                if (currcount == end):
                    break
#            else:
#                print "No See Perm: %s at %s" % (user.name, board.name)
        return ret
