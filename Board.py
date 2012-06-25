#!/usr/bin/env python
# vim: set fileencoding=utf-8 : 
from Util import Util
import Config
import struct
import json
import base64
from BCache import *
import User
import BRead
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

# PostEntry.accessed[0]
FILE_SIGN		= 0x1           #/* In article mode, Sign , Bigman 2000.8.12 ,in accessed[0] */
FILE_OWND		= 0x2          #/* accessed array */
FILE_TOTAL		= 0x2  #// aqua 2008.11.4
FILE_VISIT		= 0x4
FILE_MARKED		= 0x8
FILE_DIGEST		= 0x10      #/* Digest Mode*/  /*For SmallPig Digest Mode */
FILE_REPLIED	= 0x20       #/* in mail ,added by alex, 96.9.7 */
FILE_FORWARDED	= 0x40     #/* in mail ,added by alex, 96.9.7 */
FILE_IMPORTED	= 0x80      #/* Leeward 98.04.15 */

# not used:
# /* roy 2003.07.21 */
FILE_WWW_POST	= 0x1 #/* post by www */
FILE_ON_TOP		= 0x2 #/* on top mode */
FILE_VOTE		= 0x4 #/* article with votes */

# PostEntry.accessed[1]
#ifdef FILTER # not def
FILE_CENSOR		= 0x20        #/* for accessed[1], flyriver, 2002.9.29 */
BADWORD_IMG_FILE	= "etc/badwordv3.img"
#endif
FILE_READ		= 0x1          #/* Ownership flags used in fileheader structure in accessed[1] */
FILE_DEL		= 0x2           #/* In article mode, Sign , Bigman 2000.8.12 ,in accessed[1] */
FILE_MAILBACK	= 0x4		#/* reply articles mail to owner's mailbox, accessed[1] */
#ifdef COMMEND_ARTICLE # not def
FILE_COMMEND	= 0x8		#/* 推荐文章,stiger , in accessed[1], */
#endif
FILE_ROOTANON	= 0x10		#/* if the root article was posted anonymously, accessed[1] */

GENERATE_POST_SUFIX = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
GENERATE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

class PostEntry(CStruct):
    parser = struct.Struct('%dsIII44sH2s%ds%ds%dsIIII%dsI12s' % (Config.FILENAME_LEN, Config.OWNER_LEN, Config.OWNER_LEN, (34 - Config.OWNER_LEN), Config.STRLEN))
    _fields = [['filename', 1], 'id', 'groupid','reid', 'unsued1',
            'attachflag', 'innflag', ['owner',1, Config.OWNER_LEN], ['realowner', 1, Config.OWNER_LEN],
            'unsued2', 'rootcrc', 'eff_size', 'posttime', 'attachment',
            ['title',1, Config.ARTICLE_TITLE_LEN], 'level', ['accessed', 2, '=12B']]

    size = parser.size

    def CheckFlag(self, pos, flag):
        return bool(self.accessed[pos] & flag)

    def SetFlag(self, pos, flag, val):
        if (val):
            self.accessed[pos] |= flag
        else:
            self.accessed[pos] &= ~flag

    def IsRootPostAnonymous(self):
        return self.CheckFlag(1, FILE_ROOTANON)

    def SetRootPostAnonymous(self, rootanon):
        return self.SetFlag(1, FILE_ROOTANON, rootanon)

    def NeedMailBack(self):
        return self.CheckFlag(1, FILE_MAILBACK)

    def SetMailBack(self, need):
        return self.SetFlag(1, FILE_MAILBACK, need)

    def IsMarked(self):
        return self.CheckFlag(0, FILE_MARKED)

    def Mark(self, mark):
        return self.SetFlag(0, FILE_MARKED, mark)

    def CannotReply(self):
        return self.CheckFlag(1, FILE_READ)

    def SetCannotReply(self, val):
        return self.SetFlag(1, FILE_READ, val)

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

class Board:

    def __init__(self, bh, bs, idx):
        self.header = bh
        self.status = bs
        self.name = bh.filename
        self.index = idx

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')
        bo = None
        if (params.has_key('name')):
            name = params['name']
            bo = BoardManager.GetBoard(name)
            if (bo == None):
                raise NotFound("board not found")

        if (action == 'post_list'):
            if (bo == None):
                raise WrongArgs("lack of board name")
            if (bo.CheckReadPerm(session.GetUser())):
                bo.GetPostList(svc, session, params)
            else:
                raise NoPerm("permission denied")
        elif (action == 'list'):
            BoardManager.ListBoards(svc, session, params)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def POST(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')
        bo = None
        if (params.has_key('name')):
            name = params['name']
            bo = BoardManager.GetBoard(name)
            if (bo == None):
                raise NotFound("board %s not found" % name)
        if (action == 'clear_unread'):
            if (bo == None):
                raise WrongArgs("lack of board name")
            to = svc.get_int(params, 'to', 0)
            if (not bo.CheckReadPerm(session.GetUser())):
                raise NoPerm("permission denied")
            bo.ClearUnread(session.GetUser(), to)
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

    def GetPostList(self, svc, session, params):
        mode = Util.GetString(params, 'mode', 'normal')
        start = Util.GetInt(params, 'start')
        end = Util.GetInt(params, 'end')
        count = Util.GetInt(params, 'count')

        self.UpdateBoardInfo()
        start, end = Util.CheckRange(start, end, count, DEFAULT_GET_POST_COUNT, self.status.total)
        if ((start <= end) and (start >= 1) and (end <= self.status.total)):
            bread = BRead.BReadMgr.LoadBRead(session.GetUser().name)
            if (bread != None):
                bread.Load(self.name)
            if (mode == 'normal'):
                dirf = open(self.GetDirPath(mode), 'rb')
                post = {}
                first = True
                result = '[\n';
                for i in range(start - 1, end):
                    if (not first):
                        result += ',\n'
                    first = False
                    pe = self.GetPostEntry(i, mode, dirf)
                    post['id'] = i + 1
                    post['title'] = Util.gbkDec(pe.title)
                    post['attachflag'] = pe.attachflag
                    post['attachment'] = pe.attachment
                    post['owner'] = Util.gbkDec(pe.owner) # maybe...
                    post['posttime'] = int(pe.filename.split('.')[1])
                    post['xid'] = pe.id
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
            raise OutOfRange('out of range')
            
        return

    def GetPostEntry(self, postid, mode = 'normal', fd = None):
        pe = None
        if (postid < 0):
            return None
        try:
            if (fd == None):
                dirf = open(self.GetDirPath(mode), 'rb')
                dirf.seek(postid * PostEntry.size)
                pe = PostEntry(dirf.read(PostEntry.size))
                dirf.close()
            else:
                fd.seek(postid * PostEntry.size)
                pe = PostEntry(fd.read(PostEntry.size))
            return pe
        except Exception:
            return None

    def GetPost(self, svc, session, params, id):
        mode = Util.GetString(params, 'mode', 'normal')
        if (mode == 'junk' or mode == 'deleted'):
            raise NoPerm("invalid mode!")
        self.UpdateBoardInfo()
        if ((id >= 1) and (id <= self.status.total)):
            pe = None
            pe = self.GetPostEntry(id - 1, mode)
            postf = open(self.GetBoardPath() + pe.filename, 'rb')
            if (postf != None):
                post = {}
                post['id'] = id
                post['xid'] = pe.id
                post['title'] = Util.gbkDec(pe.title)
                post['owner'] = Util.gbkDec(pe.owner) # maybe...
                ret = ''
                while (True):
                    data = postf.read(512)
                    i = data.find('\0')
                    if (i != -1):
                        ret = ret + data[:i]
                        break
                    else:
                        ret = ret + data
                        if (len(data) < 512):
                            break

                post['content'] = Util.gbkDec(ret)

                postf.seek(0)
                attachlist = Post.GetAttachmentList(postf)
                post['picattach'] = attachlist[0]
                post['otherattach'] = attachlist[1]
                svc.writedata(json.dumps(post))
                postf.close()
                bread = BRead.BReadMgr.LoadBRead(session.GetUser().name)
                bread.Load(self.name)
                bread.MarkRead(pe.id, self.name)
            else:
                raise ServerError("fail to load posts")
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
        self.UpdateBoardInfo()
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
        self.UpdateBoardInfo()
        if ((id >= 1) and (id <= self.status.total)):
            pe = self.GetPostEntry(id - 1, mode)
            attach = Post.ReadAttachment(self.GetBoardPath() + pe.filename, offset)
            attach = {'name' : attach[0], 'content' : base64.b64encode(attach[1])}
            svc.writedata(json.dumps(attach))
        else:
            raise OutOfRange("invalid post id")

    def UpdateBoardInfo(self):
        self.status.unpack()
        return

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
            if (user.userid == 'guest'):
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

    def CheckReadonly(self):
        return self.CheckFlag(BOARD_READONLY)

    def CheckNoReply(self):
        return self.CheckFlag(BOARD_NOREPLY)

    def CanAnonyPost(self):
        return self.CheckFlag(BOARD_ANNONY)

    def CanAnonyReply(self):
        return self.CheckFlag(BOARD_ANONYREPLY)

    def IsJunkBoard(self):
        return self.CheckFlag(BOARD_JUNK)

    def DontStat(self):
        return self.CheckFlag(BOARD_POSTSTAT)

    def PreparePostArticle(self, user, refile, anony):
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

    def PostArticle(self, user, title, content, refile, signature_id, anony, mailback, session):
        # check permission
        self.PreparePostArticle(user, refile, anony)

        # filter title: 'Re: ' and '\ESC'
        title = title.replace('\033', ' ')
        if (refile == None):
            while (title[:4] == "Re: "):
                title = title[4:]

        if anony:
            if not self.MayAnonyPost(user, refile):
                anony = False

        post_file = PostEntry()
#        Log.debug("PostArticle title: %s anony: %r" % (title, anony))

        post_file.filename = self.GetPostFilename(False)
        if (not anony):
            post_file.owner = user.name
        else:
            post_file.owner = self.name
        post_file.realowner = user.name

        if (mailback):
            post_file.SetMailBack(True)

        content_encoded = content.encode('gbk')
        try:
            with open(self.GetBoardPath() + post_file.filename, "ab") as f:
                Post.WriteHeader(f, user, False, self, title, anony, 0, session)
                f.write(content_encoded)
                if (signature_id > 0 and not anony):
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

        post_file.title = title.encode('gbk')
        # TODO: outpost ('SS')
        post_file.innflag = 'LL'

        self.AfterPost(user, post_file, refile, anony)

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
        self.status.unpack()
        self.status.lastpost = last_post
        self.status.total = post_cnt
        self.status.pack()
        return True

    def GetLastPost(self):
        bdir = self.GetDirPath('normal')
        try:
            with open(bdir, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                post_cnt = size / PostEntry.size
                if (post_cnt <= 0):
                    last_post = 0
                    post_cnt = 0
                else:
                    f.seek((post_cnt - 1) * PostEntry.size, 0)
                    post_file = PostEntry(f.read(PostEntry.size))
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
            bh = BoardHeader(bh.group)

        return ret

    def WritePosts(self, user, groupid):
        if (self.name != Config.BLESS_BOARD and (not self.DontStat() or (not self.IsNormalBoard()))):
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
        myid = BCache.GetBoardNum(self.name)
        if (myid == 0):
            return False
        status = BoardStatus(myid)

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
        myid = BCache.GetBoardNum(self.name)
        if (myid == 0):
            return False
        value = 0
        if (need_update):
            value = 1

        status = BoardStatus(myid)
        if (item == 'origin'):
            status.updateorigin = value
        elif (item == 'mark'):
            status.updatemark = value
        elif (item == 'title'):
            status.updatetitle = value

        status.pack()

        return True

    def GetPostFilename(self, use_subdir):
        filename = None
        now = int(time.time())
        xlen = len(GENERATE_POST_SUFIX)
        pid = random.randint(1000, 200000) # wrong, but why care?
        for i in range(0, 10):
            if (use_subdir):
                rn = int(xlen * random.random())
                filename = "%c/M.%lu.%c%c" % (GENERATE_ALPHABET[rn], now, GENERATE_POST_SUFIX[(pid + i) % 62], GENERATE_POST_SUFIX[(pid * i) % 62])
            else:
                filename = "M.%lu.%c%c" % (now, GENERATE_POST_SUFIX[(pid + i) % 62], GENERATE_POST_SUFIX[(pid * i) % 62])
            fname = "%s/%s" % (self.GetBoardPath(), filename)
            fd = os.open(fname, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0644)
            if (fd >= 0):
                os.close(fd)
                return filename
        return None

    def DeniedUser(self, user):
        if (Util.SeekInFile(self.GetBoardPath() + "deny_users", user.name)):
            return True
        if (Util.SeekInFile(self.GetBoardPath() + "anony_deny_users", user.name)):
            return True
        return False

    def GetNextId(self):
        return BCache.GetNextID(self.name)

    def FindPost(self, id, xid, mode):
        post = self.GetPostEntry(id - 1, mode)
        if (post == None):
            post = self.GetPostEntry(0, mode)

        if (post == None):
            return None

        while (post.id != xid):
            if (post.id < xid):
                id += 1
            else:
                id -= 1
                if (id == 0):
                    return None
            post = self.GetPostEntry(id - 1, mode)
            if (post == None):
                return None

        return post

    def QuotePost(self, svc, post_id, xid, include_mode, index_mode):
        if (index_mode == 'junk' or index_mode == 'deleted'):
            raise NoPerm("invalid index_mode!")
        post = self.FindPost(post_id, xid, index_mode)
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

from Post import Post
from BoardManager import BoardManager

