from BCache import *
import json

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
                board = Board(bh, bs, i+1)
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
        if (params.has_key('board')):
            board = params['board']
            bo = BoardManager.GetBoard(board)
            if (bo == None):
                svc.send_response(404, 'Board not found')
                svc.end_headers()
                return None
            else:
                return bo
        else:
            svc.send_response(400, 'Lack of board name')
            svc.end_headers()
            return None


    @staticmethod
    def Init():
        BoardManager.LoadBoards()
        return

    @staticmethod
    def ListBoards(svc, session, params):
        start = Util.GetInt(params, 'start')
        end = Util.GetInt(params, 'end')
        count = Util.GetInt(params, 'count')

        start, end = Util.CheckRange(start, end, count, DEFAULT_LIST_BOARD_COUNT, BCache.GetBoardCount())
        print start, ' ', end
        if ((start <= end) and (start >= 1) and (end <= BCache.GetBoardCount())): 
            boards = BoardManager.GetBoards(session, start, end)
            first = True
            svc.send_response(200, 'OK %d %d' % (start, end))
            svc.end_headers()
            svc.wfile.write('[')
            for board in boards:
                board.UpdateBoardInfo()
                if (not first):
                    svc.wfile.write(',')
                first = False
                svc.wfile.write(board.GetInfoWithUserJSON(session.GetUser().name))
            svc.wfile.write(']')
            return
        else:
            svc.send_response(400, 'invalid arguments')
            svc.end_headers()
            return


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

from Board import Board
