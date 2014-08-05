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

class State(object):
    def __init__(self):
        self.locks = {}

class IndexBoardInfo(object):
    def __init__(self, board, last_idx):
        self.board = board
        self.last_idx = last_idx

class FastIndexer(threading.Thread):
    def __init__(self, state):
        threading.Thread.__init__(self)
        self.stopped = False
        self.conn = sqlite3.connect(os.path.join(Config.BBS_ROOT, INDEX_DB),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row
        self.board_info = {}
        self.load_idx_status()
        self.state = state
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

    def init_buf(self, board):
        self.conn.execute("drop table if exists %s"
                % self.buf_table_name(board))
        self.conn.execute("create table %s("\
                "id int, xid int, tid int, rid int, time int"\
                ")" % self.buf_table_name(board))
        self.conn.commit()

    def load_idx_status(self):
        self.conn.execute("create table if not exists status("\
                "board text, last_idx int)")
        self.conn.commit()
        try:
            for row in self.conn.execute("select * from status"):
                idx_info = IndexBoardInfo(**row)
                self.board_info[idx_info.board] = idx_info
        except:
            Log.info("Index info not present")

    def insert_idx_status(self, idx_obj):
        self.conn.execute("insert into status values (?, ?)",
                (idx_obj.board, idx_obj.last_idx))
        self.conn.commit()

    def remove_idx_status(self, idx_obj):
        self.conn.execute("delete from status where board=?",
                (idx_obj.board, ))
        self.conn.commit()

    def index_boards(self):
        boards = BoardManager.BoardManager.boards.keys()
        for board in boards:
            try:
                self.index_board(board)
            except Exception as exc:
                Log.error("Exception caught when indexing %s: %r"
                        % (board, exc))

    def index_board(self, board):
        """ Index one board (name: board)"""
        boardobj = BoardManager.BoardManager.GetBoard(board)
        if not boardobj:
            Log.error("Error loading board %s" % board)
            return

        if board in self.board_info:
            idx_obj = self.board_info[board]
        else:
            idx_obj = IndexBoardInfo(board, 0)
            self.board_info[board] = idx_obj

        bdir_path = boardobj.GetDirPath()
        with open(bdir_path, 'rb') as bdir:
            Util.FLock(bdir, shared=True)
            try:
                st = os.stat(bdir_path)
                if st.st_mtime <= idx_obj.last_idx:
                    # why <? anyway...
                    return

                if not board in self.state.locks:
                    self.state.locks[board] = threading.Lock()

                # index into buffer table
                self.init_buf(board)
                for idx in xrange(st.st_size / PostEntry.PostEntry.size):
                    pe = PostEntry.PostEntry(
                            bdir.read(PostEntry.PostEntry.size))
                    self.insert_entry(board, pe, idx)
                self.conn.commit()

                # commit buffer table
                self.state.locks[board].acquire()
                try:
                    self.remove_idx_status(idx_obj)
                    self.commit_buf(board)
                    idx_obj.last_idx = st.st_mtime
                    self.insert_idx_status(idx_obj)
                finally:
                    self.state.locks[board].release()
            finally:
                Util.FUnlock(bdir)

    def insert_entry(self, board, pe, idx):
        """ Insert into the buffer board """
        self.conn.execute("insert into %s values (?, ?, ?, ?, ?)"
                % self.buf_table_name(board),
                (idx, pe.id, pe.groupid, pe.reid, pe.GetPostTime()))
        # batch commit later

    def commit_buf(self, board):
        """ Rename the temporary table to final table """
        self.conn.execute("drop table if exists %s" % self.table_name(board))
        self.conn.execute("alter table %s rename to %s" %
                (self.buf_table_name(board), self.table_name(board)))
        self.conn.commit()

    def table_name(self, board):
        """ Table name for board 'board' """
        return "idx_" + board

    def buf_table_name(self, board):
        """ Temporary table name for board 'board' """
        return "tmp_idx_" + board

