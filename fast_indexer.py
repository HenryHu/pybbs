import threading
import os
import time
import sqlite3

import BoardManager
import PostEntry
import Config
from Log import Log
from Util import Util

INDEX_INTERVAL = 15
INDEX_DB = "index.db"

class IndexBoardInfo(object):
    def __init__(self, last_idx):
        self.last_idx = last_idx

class FastIndexer(threading.Thread):
    def __init__(self, state):
        threading.Thread.__init__(self)
        self.stopped = False
        self.conn = sqlite3.connect(os.path.join(Config.BBS_ROOT, INDEX_DB),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row
        self.board_info = {}
        self.state = state
        self.state.locks = {}
        try:
            self.index_boards()
        except Exception as exc:
            Log.error("Exception caught initializing FastIndexer: %r" % exc)
            raise exc

    def run(self):
        while True:
            if self.stopped:
                break
            try:
                self.index_boards()
            except Exception as exc:
                Log.error("Exception caught in FastIndexer: %r" % exc)

            time.sleep(INDEX_INTERVAL)

    def init_db(self, board):
        self.conn.execute("drop table if exists %s" % board)
        self.conn.execute("create table %s("\
                "id int, xid int, tid int, rid int, time int"\
                ")" % board)

    def index_boards(self):
        boards = BoardManager.BoardManager.boards.keys()
        for board in boards:
            try:
                self.index_board(board)
            except Exception as exc:
                Log.error("Exception caught when indexing %s: %r"
                        % (board, exc))

    def index_board(self, board):
        boardobj = BoardManager.BoardManager.GetBoard(board)
        if not boardobj:
            Log.error("Error loading board %s" % board)
            return

        if board in self.board_info:
            idx_obj = self.board_info[board]
        else:
            idx_obj = IndexBoardInfo(0)
            self.board_info[board] = idx_obj

        bdir_path = board.GetDirPath()
        with open(bdir_path, 'rb') as bdir:
            Util.FLock(bdir, shared=True)
            try:
                st = os.stat(bdir_path)
                if st.st_mtime <= idx_obj.last_idx:
                    # why <? anyway...
                    return

                if not board in self.state.locks:
                    self.state.locks[board] = threading.Lock()

                self.state.locks[board].acquire()
                try:
                    self.init_db(board)
                    for idx in xrange(st.st_size / PostEntry.PostEntry.size):
                        pe = PostEntry.PostEntry(
                                bdir.read(PostEntry.PostEntry.size))
                        self.insert_entry(board, pe, idx)
                    idx_obj.last_idx = st.st_mtime
                finally:
                    self.state.locks[board].release()
            finally:
                Util.FUnlock(bdir)

    def insert_entry(self, board, pe, idx):
        self.conn.execute("insert into %s values (?, ?, ?, ?, ?)" % board,
                (idx, pe.id, pe.groupid, pe.reid, pe.GetPostTime()))

