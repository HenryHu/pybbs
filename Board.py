#!/usr/bin/env python
# vim: set fileencoding=utf-8 : 
from Util import Util
import Config
import struct
import json
import base64
import BCache
import User
import BRead
import BoardManager
import UserManager
import PostEntry
from Error import *
from Log import Log
from cstruct import CStruct
import fcntl
import time
import os
import re
import random
import binascii
from errors import *
import digest
import store
import mmap
import searchquery
import fast_indexer

DEFAULT_GET_POST_COUNT = 20

BOARD_VOTEFLAG = 0x1
BOARD_NOZAPFLAG = 0x2
BOARD_READONLY = 0x4
BOARD_JUNK = 0x8
BOARD_ANNONY = 0x10
BOARD_OUTFLAG = 0x20  #    /* for outgo boards */
BOARD_CLUB_READ =  0x40 # /*限制读的俱乐部*/
BOARD_CLUB_WRITE = 0x80 # /*限制写的俱乐部*/
BOARD_CLUB_HIDE = 0x100 # /*隐藏俱乐部*/
BOARD_ATTACH = 0x200# /*可以使用附件的版面*/
BOARD_GROUP = 0x400  # /*目录*/
BOARD_EMAILPOST = 0x800# /* Email 发文 */
BOARD_POSTSTAT = 0x1000# /* 不统计十大 */
BOARD_NOREPLY = 0x2000 #/* 不可re文 */
BOARD_ANONYREPLY = 0x4000 #/* cannot reply anonymously */

class PostLog(CStruct):
    # what the hell! this is board name, not id! why IDLEN+6!
    # IDLEN = 12, BOARDNAMELEN = 30!
    # anyway, no one uses it...
    # change to IDLEN + 8 for padding
    parser = struct.Struct('=%dsIii' % (Config.IDLEN + 8))
    _fields = [['board', 1], 'groupid', 'date', 'number']
    size = parser.size

class PostLogNew(CStruct):
    parser = struct.Struct('=%ds%dsIii' % (Config.IDLEN + 6, Config.IDLEN + 6))
    _fields = [['userid', 1], ['board', 1], 'groupid', 'date', 'number']
    size = parser.size

class WriteDirArg:
    def __init__(self):
        self.filename = None
        self.fileptr = None
        self.ent = -1
        self.fd = None #fd: file object
        self.size = -1
        self.needclosefd = False
        self.needlock = True

    def map_dir(self):
        if self.fileptr is None:
            if self.fd is None:
                self.fd = open(self.filename, "r+b")
                self.needclosefd = True
            (self.fileptr, self.size) = Util.Mmap(
                    self.fd, mmap.PROT_READ | mmap.PROT_WRITE, mmap.MAP_SHARED)
            if self.fileptr is None:
                if self.needclosefd:
                    self.fd.close()
                return False
        return True

    def free(self):
        if self.needclosefd and self.fd is not None:
            self.fd.close()
        if self.fileptr is not None:
            self.fileptr.close()
            self.fileptr = None

class Board:

    def __init__(self, bh, bs, idx):
        self.header = bh
        self.status = bs
        self.name = bh.filename
        self.index = idx
        self.digest = digest.Digest(self, "0Announce/groups/%s" % bh.ann_path)

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')
        if not session.CheckScope('bbs'): raise NoPerm("out of scope")
        bo = None
        if (params.has_key('name')):
            name = params['name']
            bo = BoardManager.BoardManager.GetBoard(name)
            if (bo == None):
                raise NotFound("board not found")
            if (not bo.CheckReadPerm(session.GetUser())):
                raise NoPerm("permission denied")

        if action == 'list':
            BoardManager.BoardManager.ListBoards(svc, session, params)

        if bo == None:
            raise WrongArgs("lack of board name")

        if action == 'post_list':
            bo.GetPostList(svc, session, params)
        elif action == 'note' or action == 'secnote':
            result = {'content' : bo.GetNote((action == 'secnote'))}
            svc.writedata(json.dumps(result))
        elif action == 'thread_list':
            bo.GetThreadList(svc, session, params)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def POST(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')
        if not session.CheckScope('bbs'): raise NoPerm("out of scope")
        bo = None
        if (params.has_key('name')):
            name = params['name']
            bo = BoardManager.BoardManager.GetBoard(name)
            if (bo == None):
                raise NotFound("board %s not found" % name)
            if (not bo.CheckReadPerm(session.GetUser())):
                raise NoPerm("permission denied")
        if (action == 'clear_unread'):
            if (bo == None):
                Board.ClearUnreadAll(session.GetUser())
            else:
                to = svc.get_int(params, 'to', 0)
                bo.ClearUnread(session.GetUser(), to)
            result = {"result": "ok"}
            svc.writedata(json.dumps(result))
        else:
            raise WrongArgs("unknown action")

    def GetBoardPath(self, filename = ""):
        return Config.BBS_ROOT + 'boards/%s/%s' % (self.name, filename)

    def GetDirPath(self, mode = 'normal'):
        if (mode == 'normal'):
            return self.GetBoardPath() + '.DIR'
        if (mode == 'digest'):
            return self.GetBoardPath() + '.DIGEST'
        if (mode == 'mark'):
            return self.GetBoardPath() + '.MARK'
        if (mode == 'deleted'):
            return self.GetBoardPath() + '.DELETED'
        if (mode == 'junk'):
            return self.GetBoardPath() + '.JUNK'
        if (mode == 'sticky'):
            return self.GetBoardPath() + '.DINGDIR'
        if (mode == 'thread'):
            return self.GetBoardPath() + '.THREAD'
        if (mode == 'origin'):
            return self.GetBoardPath() + '.ORIGIN'

    @staticmethod
    def IsSortedMode(mode):
        return (mode == 'normal' or mode == 'thread' or mode == 'mark' or
                mode == 'origin' or mode == 'author' or mode == 'title'
                or mode == 'superfilter')

    def PostCount(self, mode = 'normal'):
        dir_path = self.GetDirPath(mode)
        try:
            st = os.stat(dir_path)
            return st.st_size / PostEntry.PostEntry.size
        except:
            return 0

    def GetPostList(self, svc, session, params):
        mode = Util.GetString(params, 'mode', 'normal')
        start = Util.GetInt(params, 'start')
        end = Util.GetInt(params, 'end')
        count = Util.GetInt(params, 'count')

        allow_empty = not start and not end

        if (mode == 'normal'):
            total = self.status.total
        else:
            total = self.PostCount(mode)

        start, end = Util.CheckRange(start, end, count, DEFAULT_GET_POST_COUNT, total)
        if ((start <= end) and (start >= 1) and (end <= total)):
            bread = BRead.BReadMgr.LoadBRead(session.GetUser().name)
            if (bread != None):
                bread.Load(self.name)
            if (mode == 'normal' or mode == 'digest' or mode == 'mark' or mode == 'sticky' or mode == 'thread' or mode == 'origin'):
                dirf = open(self.GetDirPath(mode), 'rb')
                post = {}
                first = True
                result = '[\n'
                for i in range(start - 1, end):
                    pe = self.GetPostEntry(i, mode, dirf)
                    if (pe is None):
                        continue
                    if (not first):
                        result += ',\n'
                    first = False
                    post = pe.GetInfoExtended(session.GetUser(), self, 'post')
                    post['id'] = i + 1
                    read = True
                    if (bread != None):
                        read = not bread.QueryUnread(pe.id, self.name)
                    post['read'] = read
#                    post['filename'] = pe.filename
                    result += json.dumps(post, 'utf-8')
                result += '\n]'
                svc.writedata(result)
                dirf.close()
        else:
            if allow_empty:
                svc.writedata('[]')
            else:
                raise OutOfRange('out of range')
            
        return

    def GetPostEntry(self, postid, mode = 'normal', fd = None):
        pe = None
        if (postid < 0):
            return None
        try:
            if (fd == None):
                dirf = open(self.GetDirPath(mode), 'rb')
                dirf.seek(postid * PostEntry.PostEntry.size)
                pe = PostEntry.PostEntry(dirf.read(PostEntry.PostEntry.size))
                dirf.close()
            else:
                fd.seek(postid * PostEntry.PostEntry.size)
                pe = PostEntry.PostEntry(fd.read(PostEntry.PostEntry.size))
            return pe
        except Exception:
            return None

    def GetPost(self, svc, session, params, id, start, count):
        mode = Util.GetString(params, 'mode', 'normal')
        if (mode == 'junk' or mode == 'deleted'):
            raise NoPerm("invalid mode!")
        if ((id >= 1) and (id <= self.status.total)):
            pe = self.GetPostEntry(id - 1, mode)
            postpath = self.GetBoardPath() + pe.filename
            post = pe.GetInfo('post')
            post['id'] = id
            postinfo = Post(postpath, pe)
            post = dict(post.items() + postinfo.GetInfo(start, count).items())
            if (post['picattach'] or post['otherattach']):
                post['attachlink'] = Post.GetAttachLink(session, self, pe)
            svc.writedata(json.dumps(post))
            bread = BRead.BReadMgr.LoadBRead(session.GetUser().name)
            bread.Load(self.name)
            bread.MarkRead(pe.id, self.name)
        else:
            raise OutOfRange("invalid post id")

        return

    def GetNextPostReq(self, svc, session, params, id):
        direction = Util.GetString(params, 'direction', 'forward')
        bfwd = True
        if (direction == 'backward'):
            bfwd = False

        last_one = bool(svc.get_int(params, 'last_one', 0))
        only_new = bool(svc.get_int(params, 'only_new', 0))
        
        next_id = self.GetNextPost(id, bfwd, last_one, only_new, session.GetUser())
        if next_id < 1:
            raise ServerError("fail to get next post")
        else:
            nextinfo = {}
            nextinfo['nextid'] = next_id
            svc.writedata(json.dumps(nextinfo))

    def GetNextPost(self, id, forward, last_one, only_new, user):
        if ((id >= 1) and (id <= self.status.total)):
            last_post = -1
            dirf = open(self.GetDirPath("normal"), 'rb')
            if (dirf == None):
                raise ServerError("fail to load post")
            pe = self.GetPostEntry(id - 1, "normal", dirf)
            if (forward):
                i = id + 1
            else:
                i = id - 1
            if (only_new):
                bread = BRead.BReadMgr.LoadBRead(user.name)
            while ((i >= 1) and (i <= self.status.total)):
                pxe = self.GetPostEntry(i - 1, "normal", dirf)
                if (pxe.groupid == pe.groupid):
                    if ((only_new and bread.QueryUnread(pxe.id, self.name)) or (not only_new)):
                        if (not last_one):
                            dirf.close()
                            return i
                        else:
                            last_post = i
                    if (pxe.groupid == pxe.id): # original post
                        break
                if (forward):
                    i = i + 1
                else:
                    i = i - 1
            dirf.close()
            if (last_one):
                if (last_post != -1):
                    return last_post
                else:
                    raise NotFound("post not found")
            else:
                raise NotFound("post not found")
        else:
            raise OutOfRange("invalid post id")

    def GetAttachmentReq(self, svc, session, params, id):
        mode = Util.GetString(params, 'mode', 'normal')
        offset = Util.GetInt(params, 'offset')
        if (offset <= 0):
            raise WrongArgs("invalid or lacking offset")
        if ((id >= 1) and (id <= self.status.total)):
            pe = self.GetPostEntry(id - 1, mode)
            attach = Post.ReadAttachment(self.GetBoardPath() + pe.filename, offset)
            attach = {'name' : attach[0], 'content' : base64.b64encode(attach[1])}
            svc.writedata(json.dumps(attach))
        else:
            raise OutOfRange("invalid post id")

    def GetInfo(self):
        rboard = {}
        rboard['name'] = self.name
        title = self.GetTitle()
        result = re.match('([0-9 ]*)\[([^]]*)\] *([^ ]*) *(.*)', title)
        rboard['major'] = result.group(1)
        rboard['minor'] = result.group(2)
        rboard['outpost'] = result.group(3)
        rboard['desc'] = result.group(4)
        rboard['id'] = self.index
        rboard['BM'] = self.GetBM()
        rboard['total'] = self.GetTotal()
        rboard['currentusers'] = self.GetCurrentUsers()
        rboard['anony_post'] = int(self.CanAnonyPost())
        rboard['anony_reply'] = int(self.CanAnonyReply())
        rboard['group'] = self.GetGroup()
        if self.IsDir():
            rboard['isdir'] = self.IsDir()
            rboard['child_count'] = self.GetChildCount()
        return rboard

    def GetInfoWithUser(self, user):
        rboard = self.GetInfo()
        rboard['read'] = not self.GetUnread(user)
        return rboard

    def GetInfoWithUserJSON(self, user):
        return json.dumps(self.GetInfoWithUser(user))

    def GetInfoJSON(self):
        return json.dumps(self.GetInfo())

    def CheckReadPerm(self, user):
        if (self.header == None):
            return False

        level = self.header.level
        if ((level & User.PERM_POSTMASK != 0) or (user.HasPerm(level)) or (level & User.PERM_NOZAP != 0)):
            if (self.CheckFlag(BOARD_CLUB_READ)):
                if (user.HasPerm(User.PERM_OBOARDS) and user.HasPerm(User.PERM_SYSOP)):
                    return True
                if (self.header.clubnum <= 0 or self.header.clubnum >= Config.MAXCLUB):
                    return False
                if (user.CanReadClub(self.header.clubnum)):
                    return True

                return False

            else:
                return True

        return False

    def CheckFlag(self, flag):
        if (self.header.flag & flag != 0):
            return True
        return False;

    def CheckPostPerm(self, user):
        if (self.header == None):
            return False

        if (self.CheckFlag(BOARD_GROUP)):
            return False

        if (not user.HasPerm(User.PERM_POST)):
            if (user.name == 'guest'):
                return False
            if (self.name == "BBShelp"):
                return True # not exist here
            if (not user.HasPerm(User.PERM_LOGINOK)):
                return False
            if (self.name == "Complain"):
                return True # not exist here
            if (self.name == "sysop"):
                return True
            if (self.name == "Arbitration"):
                return True # not exist here
            return False

        if (self.header.level == 0 or user.HasPerm(self.header.level & ~User.PERM_NOZAP & ~User.PERM_POSTMASK)):
            if (self.CheckFlag(BOARD_CLUB_WRITE)):
                if (self.header.clubnum <= 0 or self.header.clubnum >= Config.MAXCLUB):
                    return False
                return user.CanPostClub(self.header.clubnum)
            else:
                return True
        else:
            return False

    def CheckSeePerm(self, user):
        if (self.header == None):
            return False
        if (user == None):
            if (self.header.title_level != 0):
                return False
        else:
            if (not user.HasPerm(User.PERM_OBOARDS) and self.header.title_level != 0 and self.header.title_level != user.GetTitle()):
                return False
            level = self.header.level
            if (level & User.PERM_POSTMASK != 0 
                    or (user == None and level == 0)
                    or (user != None and user.HasPerm(level))
                    or (level & User.PERM_NOZAP != 0)):
                if (self.CheckFlag(BOARD_CLUB_HIDE)):
                    if (user == None): return False
                    if (user.HasPerm(User.PERM_OBOARDS)): return True
                    return self.CheckReadPerm(user)
                return True

        return False

    def GetTitle(self):
        return Util.gbkDec(self.header.title)

    def GetBM(self):
        return self.header.BM

    def GetTotal(self):
        return self.status.total

    def GetCurrentUsers(self):
        return self.status.currentusers

    def GetLastPostId(self):
        return self.status.lastpost

    def LoadBReadFor(self, user):
        bread = BRead.BReadMgr.LoadBRead(user.name)
        if (bread == None):
            return None
        succ = bread.Load(self.name)
        if (not succ):
            return None
        return bread

    def GetUnread(self, user):
        bread = self.LoadBReadFor(user)
        if (bread is None):
            return True
        return bread.QueryUnread(self.GetLastPostId(), self.name)

    def ClearUnread(self, user, to = 0):
        bread = self.LoadBReadFor(user)
        if (bread is None):
            return True
        if (to == 0):
            return bread.Clear(self.name)
        else:
            return bread.ClearTo(to, self.name)

    @staticmethod
    def ClearUnreadAll(user):
        for i in xrange(BCache.BCache.GetBoardCount()):
            board = BoardManager.BoardManager.GetBoardByIndex(i)
            if (board is not None):
                board.ClearUnread(user)

    def CheckReadonly(self):
        return self.CheckFlag(BOARD_READONLY)

    def CheckNoReply(self):
        return self.CheckFlag(BOARD_NOREPLY)

    def CanAnonyPost(self):
        return self.CheckFlag(BOARD_ANNONY)

    def CanAnonyReply(self):
        return self.CheckFlag(BOARD_ANONYREPLY)

    def CanPostAttach(self):
        return self.CheckFlag(BOARD_ATTACH)

    def IsJunkBoard(self):
        return self.CheckFlag(BOARD_JUNK)

    def IsSysmailBoard(self):
        return self.name == Config.SYSMAIL_BOARD

    def DontStat(self):
        return self.CheckFlag(BOARD_POSTSTAT)

    def PreparePostArticle(self, user, refile, anony, attach):
        detail = {}
        if (refile != None):
            if (self.CheckNoReply()):
                raise NoPerm("can't reply in this board")
            if (refile.CannotReply()):
                raise NoPerm("can't reply this post")
        if (self.CheckReadonly()):
            Log.debug("PostArticle: fail: readonly")
            raise NoPerm("board is readonly")
        if (not self.CheckPostPerm(user)):
            Log.debug("PostArticle: fail: %s can't post on %s" % (user.name, self.name))
            raise NoPerm("no permission to post")
        if (self.DeniedUser(user)):
            if (not user.HasPerm(User.PERM_SYSOP)):
                Log.debug("PostArticle: fail: %s denied on %s" % (user.name, self.name))
                raise NoPerm("user denied")

        if anony:
            if not self.MayAnonyPost(user, refile):
                detail['anonymous'] = 1

        if attach:
            if not self.CanPostAttach():
                detail['attachment'] = 1

        return detail

    def MayAnonyPost(self, user, refile):
        mycrc = (~binascii.crc32(user.name, 0xffffffff)) & 0xffffffff

        may_anony = False
        if (refile == None): # not in reply mode
            if (self.CanAnonyPost()):
                may_anony = True
        else:
            if (self.CanAnonyPost() and mycrc == refile.rootcrc):
                may_anony = True
            else:
                if (self.CanAnonyReply()):
                    may_anony = True

        return may_anony

    def PostArticle(self, user, title, content, refile, signature_id, anony, mailback, session, attach, ignoreperm = False):
        # check permission
        if not ignoreperm:
            self.PreparePostArticle(user, refile, anony, attach)

        # filter title: 'Re: ' and '\ESC'
#        title = title.replace('\033', ' ')
        title = re.sub('[\x00-\x19]', ' ', title)
        if (refile == None):
            while (title[:4] == "Re: "):
                title = title[4:]

        if anony:
            if not self.MayAnonyPost(user, refile):
                anony = False

        if attach:
            if not self.CanPostAttach():
                attach = None

        post_file = PostEntry.PostEntry()
#        Log.debug("PostArticle title: %s anony: %r" % (title, anony))

        post_file.filename = self.GetPostFilename(False)
        if (not anony):
            post_file.owner = user.name
        else:
            post_file.owner = self.name
        post_file.realowner = user.name

        if (mailback):
            post_file.SetMailBack(True)

        content_encoded = Util.gbkEnc(content)
        try:
            with open(self.GetBoardPath() + post_file.filename, "ab") as f:
                Post.WriteHeader(f, user, False, self, title, anony, 0, session)
                f.write(content_encoded)
                if (not anony):
                    Post.AddSig(f, user, signature_id)
        except IOError:
            Log.error("PostArticle: write post failed!")
            os.unlink(self.GetBoardPath() + post_file.filename)
            raise ServerError("fail to write post file")

        post_file.eff_size = len(content_encoded)

        if (refile != None):
            post_file.rootcrc = refile.rootcrc
            if (refile.IsRootPostAnonymous()):
                post_file.SetRootPostAnonymous(True)
        else:
            mycrc = (~binascii.crc32(user.name, 0xffffffff)) & 0xffffffff
            post_file.rootcrc = mycrc
            if (anony):
                post_file.SetRootPostAnonymous(True)

        if (signature_id == 0):
            has_sig = False
        else:
            has_sig = True
        Post.AddLogInfo(self.GetBoardPath(post_file.filename), user, session, anony, has_sig)

        post_file.title = Util.gbkEnc(title)
        # TODO: outpost ('SS')
        post_file.innflag = 'LL'

        if attach:
            try:
                post_file.attachment = len(attach)
            except:
                post_file.attachment = 0
        else:
            post_file.attachment = 0

        self.AfterPost(user, post_file, refile, anony)

        if attach:
            try:
                for att in attach:
                    filename = att['name']
                    tmpfile = att['store_id']
                    if (not store.Store.verify_id(tmpfile)):
                        continue

                    tmpfile = store.Store.path_from_id(tmpfile)

                    Post.AddAttach(self.GetBoardPath(post_file.filename), filename, tmpfile)
            except:
                pass

        if (not self.IsJunkBoard()):
            user.AddNumPosts()

        return True

    def AfterPost(self, user, post_file, re_file, anony):
        bdir = self.GetDirPath('normal')

        try:
            with open(bdir, "ab") as bdirf:
                fcntl.flock(bdirf, fcntl.LOCK_EX)
                try:
                    nowid = self.GetNextId()
                    if (nowid < 0):
                        raise IOError()
                    post_file.id = nowid
                    if (re_file == None):
                        post_file.groupid = nowid
                        post_file.reid = nowid
                    else:
                        post_file.groupid = re_file.groupid
                        post_file.reid = re_file.id

                    post_file.posttime = 0 # not used
                    # no seek: append mode
                    bdirf.write(post_file.pack())
                finally:
                    fcntl.flock(bdirf, fcntl.LOCK_UN)

        except IOError as e:
            post_fname = self.GetBoardPath() + post_file.filename
            os.unlink(post_fname)
            raise e

        self.UpdateLastPost()

        bread = BRead.BReadMgr.LoadBRead(user.name)
        if (bread != None):
            bread.Load(self.name)
            bread.MarkRead(post_file.id, self.name)

        if (re_file != None):
            if (re_file.NeedMailBack()):
                # mail back, not implemented
                pass

        if (user != None and anony):
            # ANONYDIR: not used, ignore it
            pass

        if (user != None and not anony):
            self.WritePosts(user, post_file.groupid)

        if (post_file.id == post_file.groupid):
            # self.RegenSpecial('origin': later)
            self.SetUpdate('origin', True)

        self.SetUpdate('title', True)
        if (post_file.IsMarked()):
            self.SetUpdate('mask', True)

        # log: later
        return

    def UpdateLastPost(self):
        (post_cnt, last_post) = self.GetLastPost()
#        self.status.unpack()
        self.status.lastpost = last_post
        self.status.total = post_cnt
#        self.status.pack()
        return True

    def GetLastPost(self):
        bdir = self.GetDirPath('normal')
        try:
            with open(bdir, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                post_cnt = size / PostEntry.PostEntry.size
                if (post_cnt <= 0):
                    last_post = 0
                    post_cnt = 0
                else:
                    f.seek((post_cnt - 1) * PostEntry.PostEntry.size, 0)
                    post_file = PostEntry.PostEntry(f.read(PostEntry.PostEntry.size))
                    last_post = post_file.id

                return (post_cnt, last_post)
        except IOError:
            return (0, 0)

    def IsNormalBoard(self):
        if (self.name == Config.DEFAULTBOARD):
            return True

        bh = self.header
        ret = True
        while (ret):
            ret = not (bh.level & User.PERM_SYSOP) and not (bh.flag & BOARD_CLUB_HIDE) and not (bh.flag & BOARD_CLUB_READ)
            if (bh.title_level != 0):
                ret = False
            if (not ret or (bh.group == 0)):
                break
            bh = BCache.BoardHeader(bh.group)

        return ret

    def WritePosts(self, user, groupid):
        if (self.name != Config.BLESS_BOARD and (self.DontStat() or (not self.IsNormalBoard()))):
            return 0
        now = time.time()

        postlog = PostLog()
        postlog.board = self.name
        postlog.groupid = groupid
        postlog.date = now
        postlog.number = 1

        postlog_new = PostLogNew()
        postlog_new.board = self.name
        postlog_new.groupid = groupid
        postlog_new.date = now
        postlog_new.number = 1
        postlog_new.userid = user.name

        xpostfile = "%s/tmp/Xpost/%s" % (Config.BBS_ROOT, user.name)

        log = True
        try:
            with open(xpostfile, "rb") as fp:
                while (True):
                    pl_data = fp.read(PostLog.size)
                    if (len(pl_data) < PostLog.size):
                        break

                    pl = PostLog(pl_data)
                    if (pl.groupid == groupid and pl.board == self.name):
                        log = False
                        break
        except IOError:
            pass

        if (log):
            Util.AppendRecord(xpostfile, postlog.pack())
            Util.AppendRecord(Config.BBS_ROOT + "/.newpost", postlog.pack())
            Util.AppendRecord(Config.BBS_ROOT + "/.newpost_new", postlog_new.pack())

        return 0

    def GetUpdate(self, item):
        myid = BCache.BCache.GetBoardNum(self.name)
        if (myid == 0):
            return False
        status = BCache.BoardStatus(myid)

        value = 0
        if (item == 'origin'):
            value = status.updateorigin
        elif (item == 'mark'):
            value = status.updatemark
        elif (item == 'title'):
            value = status.updatetitle

        if (value == 0):
            return False
        return True

    def SetUpdate(self, item, need_update):
        myid = BCache.BCache.GetBoardNum(self.name)
        if (myid == 0):
            return False
        value = 0
        if (need_update):
            value = 1

        status = BCache.BoardStatus(myid)
        if (item == 'origin'):
            status.updateorigin = value
        elif (item == 'mark'):
            status.updatemark = value
        elif (item == 'title'):
            status.updatetitle = value

#        status.pack()

        return True

    def GetPostFilename(self, use_subdir):
        return Post.GetPostFilename(self.GetBoardPath(), use_subdir)

    def DeniedUser(self, user):
        if (Util.SeekInFile(self.GetBoardPath() + "deny_users", user.name)):
            return True
        if (Util.SeekInFile(self.GetBoardPath() + "anony_deny_users", user.name)):
            return True
        return False

    def GetNextId(self):
        return BCache.BCache.GetNextID(self.name)

    def FindPost(self, id, xid, mode):
        if id > 0:
            post = self.GetPostEntry(id - 1, mode)
            for i in xrange(5):
                if post is None:
                    break
                if post.id == xid:
                    return (post, id)
                if post.id < xid:
                    id += 1
                else:
                    id -= 1
                post = self.GetPostEntry(id - 1, mode)

        count = self.PostCount(mode)
        start = 1
        end = count

        while end >= start:
            mid = (start + end) / 2
            post = self.GetPostEntry(mid - 1, mode)
            if post.id < xid:
                start = mid + 1
            elif post.id > xid:
                end = mid - 1
            else:
                return (post, mid)

        return (None, 0)

    def QuotePost(self, svc, post_id, xid, include_mode, index_mode):
        if (index_mode == 'junk' or index_mode == 'deleted'):
            raise NoPerm("invalid index_mode!")
        (post, _) = self.FindPost(post_id, xid, index_mode)
        if (post == None):
            raise NotFound("referred post not found")
        quote = Post.DoQuote(include_mode, self.GetBoardPath(post.filename), True)
        if (post.title[:3] == "Re:"):
            quote_title = post.title
        elif (post.title[:3] == u"├ ".encode('gbk')):
            quote_title = "Re: " + post.title[3:]
        elif (post.title[:3] == u"└ ".encode('gbk')):
            quote_title = "Re: " + post.title[3:]
        else:
            quote_title = "Re: " + post.title
        quote_obj = {}
        quote_obj['title'] = Util.gbkDec(quote_title)
        quote_obj['content'] = Util.gbkDec(quote)
        svc.writedata(json.dumps(quote_obj))

    def GetNote(self, secret = False):
        if (not secret):
            notes_path = "%s/vote/%s/notes" % (Config.BBS_ROOT, self.name)
        else:
            notes_path = "%s/vote/%s/secnotes" % (Config.BBS_ROOT, self.name)

        try:
            with open(notes_path, 'rb') as f:
                return Util.gbkDec(f.read())
        except:
            raise NotFound('board note does not exist')

    @staticmethod
    def IsBM(user, bmstr):
        if (user.IsSuperBM() or user.IsSysop()):
            return True
        if (not user.IsBM()):
            return False
        return Board.IsBMs(user.name, bmstr)

    @staticmethod
    def IsBMs(userid, bmstr):
        for item in re.split('[,: ;|&()\0\n]', bmstr):
            if (userid == item):
                return True
        return False

    def IsMyBM(self, user):
        bmstr = self.GetBM()
        return Board.IsBM(user, bmstr)

    def IsDir(self):
        return (self.header.flag & BOARD_GROUP) != 0

    def GetChildCount(self):
        if not self.IsDir():
            return 0
        return self.header.adv_club # it's a union, in fact

    def GetGroup(self):
        return self.header.group

    def DelPost(self, user, post_id, post_xid, mode = 'normal'):
        # from del_post()
        if post_id > self.PostCount(mode):
            raise WrongArgs("out of range")
        if self.name == "syssecurity" or self.name == "junk" or self.name == "deleted":
            raise WrongArgs("invalid board: %s" % self.name)
        if mode == "junk" or mode == "deleted":
            raise WrongArgs("invalid mode: %s" % mode)
        (post_entry, new_post_id) = self.FindPost(post_id, post_xid, mode)
        if post_entry is None:
            raise NotFound("post not found")
        if not post_entry.CanBeDeleted(user, self):
            raise NoPerm("permission denied")
        owned = user.IsOwner(post_entry)

        arg = WriteDirArg()
        arg.filename = self.GetDirPath(mode)
        if mode == 'normal' or mode == 'digest':
            arg.ent = new_post_id

        # from do_del_post()
        succ = self.PrepareWriteDir(arg, mode, post_entry)
        if not succ:
            raise ServerError("fail to prepare directory write")
        self.DeleteEntry(arg.fileptr, arg.ent, arg.size, arg.fd)
        Util.FUnlock(arg.fd)

        self.SetUpdate('title', True)
        self.CancelPost(user, post_entry, owned, True)
        self.UpdateLastPost()
        if post_entry.IsMarked():
            self.SetUpdate('mark', True)
        if mode == 'normal' and not (post_entry.IsMarked() and post_entry.CannotReply() and post_entry.IsForwarded()) and not self.IsJunkBoard():
            if owned:
                user.DecNumPosts()
            elif not "." in post_entry.owner and Config.BMDEL_DECREASE:
                user = UserManager.UserManager.LoadUser(post_entry.owner)
                if user is not None and not self.IsSysmailBoard():
                    user.DecNumPosts()

        arg.free()

    def PrepareWriteDir(self, arg, mode = 'normal', post_entry = None):
        if not arg.map_dir():
            return False
        if arg.needlock:
            Util.FLock(arg.fd)
        if post_entry:
            (newpost, newid) = self.FindPost(arg.ent, post_entry.id, mode)
            if newpost is None:
                Util.FUnlock(arg.fd)
                return False
            arg.ent = newid
        return True

    def DeleteEntry(self, fileptr, entry, size, fd):
        dst_pos = PostEntry.PostEntry.size * (entry - 1)
        src_pos = PostEntry.PostEntry.size * entry
        new_size = size - PostEntry.PostEntry.size
        fileptr[dst_pos:new_size] = fileptr[src_pos:size]
        os.ftruncate(fd.fileno(), new_size)

    def UpdatePostEntry(self, post_entry, post_id = 0, mode = 'normal'):
        arg = WriteDirArg()
        arg.filename = self.GetDirPath(mode)
        succ = self.PrepareWriteDir(arg, mode, post_entry)
        if not succ:
            return False
        try:
            pos = PostEntry.PostEntry.size * (arg.ent - 1)
            arg.fileptr[pos:pos+PostEntry.PostEntry.size] = post_entry.pack()
        finally:
            arg.free()
        return True

    def CancelPost(self, user, entry, owned, append):
        # TODO: delete mail

        # rename post file
        new_filename = entry.filename
        rep_char = 'J' if owned else 'D'
        if new_filename[1] == '/':
            new_filename = entry.filename[0] + rep_char + entry.filename[2:]
        else:
            new_filename = rep_char + entry.filename[1:]

        oldpath = self.GetBoardPath(entry.filename)
        newpath = self.GetBoardPath(new_filename)
        os.rename(oldpath, newpath)

        entry.filename = new_filename
        new_title = "%-32.32s - %s" % (entry.title, user.name)

        if not append:
            entry.title = new_title
            entry.UpdateDeleteTime()
            # TODO: flush back entry changes
        else:
            postfile = PostEntry.PostEntry()

            postfile.filename = new_filename
            postfile.owner = entry.owner
            postfile.id = entry.id
            postfile.groupid = entry.groupid
            postfile.reid = entry.reid
            postfile.attachment = entry.attachment
            postfile.title = new_title
            postfile.UpdateDeleteTime()

            new_dir = self.GetDirPath('junk' if owned else 'deleted')
            Util.AppendRecord(new_dir, postfile.pack())

        return True

    def EditPost(self, session, post_xid, post_id = 0, new_title = None,
            content = None, mode = 'normal', attach_to_remove = set(),
            add_attach_list = []):
        (post_entry, post_id) = self.FindPost(post_id, post_xid, mode)
        if post_entry is None:
            raise NotFound("post not found")
        if (self.name == "syssecurity" or self.name == "junk"
                or self.name == "deleted"):
            raise WrongArgs("can't edit post in board %s" % self.name)
        if mode == "junk" or mode == "deleted":
            raise WrongArgs("can't edit post in mode %s" % mode)
        if self.CheckReadonly():
            raise WrongArgs("board %s is read-only" % self.name)
        user = session.GetUser()
        if not post_entry.CanBeEdit(user, self):
            raise NoPerm("you can't edit this post")
        if self.DeniedUser(user):
            raise NoPerm("you can't edit on board %s" % self.name)

        post_path = self.GetBoardPath(post_entry.filename);
        post = Post(post_path, post_entry)

        if content is None:
            content = post.GetBody()

        first_attach_pos = 0
        need_update = False
        new_post_path = post_path + ".new"

        if new_title is not None and new_title != Util.gbkDec(post_entry.title):
            post_entry.title = Util.gbkEnc(new_title)
            need_update = True

        with open(post_path, "r+b") as postf:
            Util.FLock(postf)
            try:
                attach_list = post.GetAttachList()

                newpost = Post(new_post_path, post_entry)
                newpost.open()
                try:
                    newpost.EditHeaderFrom(post, new_title)
                    size_header = newpost.pos()
                    newpost.EditContent(content, session, post)
                    content_len = newpost.pos() - size_header
                    if content_len != post_entry.eff_size:
                        post_entry.eff_size = content_len
                        need_update = True

                    # copy original attachments
                    orig_attach_id = 0
                    for attach_entry in attach_list:
                        if not orig_attach_id in attach_to_remove:
                            try:
                                attach_pos = newpost.AppendAttachFrom(post, attach_entry)
                                if first_attach_pos == 0:
                                    first_attach_pos = attach_pos
                            except:
                                pass
                        orig_attach_id += 1

                    # add new attachments
                    for attach_entry in add_attach_list:
                        filename = attach_entry['name']
                        tmpfile = attach_entry['store_id']
                        if (not store.Store.verify_id(tmpfile)):
                            continue
                        tmpfile = store.Store.path_from_id(tmpfile)

                        try:
                            attach_pos = newpost.AddAttachSelf(filename, tmpfile)
                            if first_attach_pos == 0:
                                first_attach_pos = attach_pos
                        except Exception as e:
                            Log.warn("fail to add attach: %r" % e)
                finally:
                    newpost.close()

                os.rename(new_post_path, post_path)
            finally:
                try:
                    os.remove(new_post_path)
                except:
                    pass
                Util.FUnlock(postf)

        if first_attach_pos != post_entry.attachment:
            post_entry.attachment = first_attach_pos
            need_update = True

        if need_update:
            # fail to update post info is not that important
            if not self.UpdatePostEntry(post_entry, post_id, mode):
                Log.warn("fail to update post entry!")

    def SearchPost(self, user, start_id, forward, query_expr, count = 1):
        if count > Config.SEARCH_COUNT_LIMIT:
            count = Config.SEARCH_COUNT_LIMIT
        result = []
        curr_id = start_id
        result_count = 0
        query = searchquery.SearchQuery(query_expr)
        while True:
            post_entry = self.GetPostEntry(curr_id - 1)
            if post_entry is None:
                return result

            if query.match(self, post_entry):
                info = post_entry.GetInfoExtended(user, self)
                info['id'] = curr_id
                result.append(info)
                result_count += 1
                if result_count == count:
                    return result

            if forward:
                curr_id += 1
            else:
                curr_id -= 1
        return result

    def GetThreadList(self, svc, session, param):
        """ handle board/thread_list
            List posts in the thread 'tid'.
            From the 'start'th post in the thread, return 'count' results.
            If mode is:
                'idonly': only return id and xid
                'compact': return post info
                'detailed': also return post content, return at most
                    'max_length' characters for each post
            Return a list of posts. """

        start = svc.get_int(param, 'start', 0)
        count = svc.get_int(param, 'count', 10)
        tid = svc.get_int(param, 'tid')
        mode = svc.get_str(param, 'mode', 'idonly')
        content_len = svc.get_str(param, 'max_length', 200)

        result = fast_indexer.query_by_tid(svc.server.fast_indexer_state,
                self.name, tid, start, count)

        ret = []
        for (post_id, post_xid) in result:
            if mode == 'idonly':
                ret.append({'id': post_id, 'xid': post_xid})
            else:
                (post_entry, cur_post_id) = self.FindPost(
                        post_id, post_xid, 'normal')
                if post_entry is None:
                    # deleted after last index?
                    continue
                post_info = post_entry.GetInfoExtended(session.GetUser(), self)
                post_info['id'] = cur_post_id
                if mode == 'detailed':
                    postpath = self.GetBoardPath() + post_entry.filename
                    postobj = Post(postpath, post_entry)
                    post_info = dict(post_info.items()
                            + postobj.GetInfo(0, content_len).items())
                    if (post_info['picattach'] or post_info['otherattach']):
                        post_info['attachlink'] = Post.GetAttachLink(
                                session, self, post_entry)
                    # mark the post as read
                    # only in detailed mode
                    bread = BRead.BReadMgr.LoadBRead(session.GetUser().name)
                    bread.Load(self.name)
                    bread.MarkRead(post_xid, self.name)
                ret.append(post_info)

        svc.writedata(json.dumps({'result': 'ok', 'list': ret}))

from Post import Post

