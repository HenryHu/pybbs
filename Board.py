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
# not used
FILE_OWND		= 0x2          #/* accessed array */
# combined into big post
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

    def IsReplied(self):
        return self.CheckFlag(0, FILE_REPLIED)

    def IsForwarded(self):
        return self.CheckFlag(0, FILE_FORWARDED)

    def InDigest(self):
        return self.CheckFlag(0, FILE_DIGEST)

    def IsRead(self):
        return self.CheckFlag(0, FILE_READ)

    def UpdateDeleteTime(self):
        self.accessed[-1] = int(time.time()) / (3600 * 24) % 100;

    def GetPostTime(self):
        return int(self.filename.split('.')[1])

    def GetInfo(self, mode = 'post'):
        post = {'title': Util.gbkDec(self.title)}
        post['attachflag'] = self.attachflag
        post['attachment'] = self.attachment
        post['owner'] = Util.gbkDec(self.owner)
        try:
            post['posttime'] = self.GetPostTime()
        except:
            post['posttime'] = 0
        flags = []
        if (self.IsMarked()):
            flags += ['marked']
        if (mode == 'post'):
            post['xid'] = self.id
            post['thread'] = self.groupid
            post['reply_to'] = self.reid
            post['size'] = self.eff_size
            if (self.CannotReply()):
                flags += ['noreply']
            if (self.InDigest()):
                flags += ['g']
        if (mode == 'mail'):
            if (self.IsReplied()):
                flags += ['replied']
            if (self.IsForwarded()):
                flags += ['forwarded']
            if (self.IsRead()):
                post['read'] = True
            else:
                post['read'] = False

        post['flags'] = flags

        return post

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

        if (action == 'post_list'):
            if (bo == None):
                raise WrongArgs("lack of board name")
            bo.GetPostList(svc, session, params)
        elif (action == 'list'):
            BoardManager.BoardManager.ListBoards(svc, session, params)
        elif (action == 'note' or action == 'secnote'):
            if (bo == None):
                raise WrongArgs("lack of board name")
            result = {'content' : bo.GetNote((action == 'secnote'))}
            svc.writedata(json.dumps(result))
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
            return st.st_size / PostEntry.size
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
                    post = pe.GetInfo('post')
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
        if ((id >= 1) and (id <= self.status.total)):
            pe = self.GetPostEntry(id - 1, mode)
            postpath = self.GetBoardPath() + pe.filename
            post = pe.GetInfo('post')
            post['id'] = id
            postinfo = Post(postpath)
            post = dict(post.items() + postinfo.GetInfo().items())
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

    def PostArticle(self, user, title, content, refile, signature_id, anony, mailback, session, attach):
        # check permission
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
        return BCache.BCache.GetNextID(self.name)

    def FindPost(self, id, xid, mode):
        post = self.GetPostEntry(id - 1, mode)
        if (post == None):
            post = self.GetPostEntry(0, mode)

        if (post == None):
            return (None, 0)

        while (post.id != xid):
            if (post.id < xid):
                id += 1
            else:
                id -= 1
                if (id == 0):
                    return (None, 0)
            post = self.GetPostEntry(id - 1, mode)
            if (post == None):
                return (None, 0)

        return (post, id)

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

    def DelPost(self, user, post_id, mode = 'normal'):
        # from del_post()
        if post_id > self.PostCount(mode):
            return False
        if self.name == "syssecurity" or self.name == "junk" or self.name == "deleted":
            return False
        if mode == "junk" or mode == "deleted":
            return False
        post_entry = self.GetPostEntry(post_id, mode)
        owned = user.IsOwner(post_entry)
        if not owned and not user.IsSysop() and not self.IsMyBM(user):
            return False

        arg = WriteDirArg()
        arg.filename = self.GetDirPath(mode)
        if mode == 'normal' or mode == 'digest':
            arg.ent = post_id

        # from do_del_post()
        succ = self.PrepareWriteDir(arg, mode, post_entry)
        if not succ:
            return False
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
        return True

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
        dst_pos = PostEntry.size * (entry - 1)
        src_pos = PostEntry.size * entry
        new_size = size - PostEntry.size
        fileptr[dst_pos:new_size] = fileptr[src_pos:size]
        os.ftruncate(fd.fileno(), new_size)

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
            postfile = PostEntry()

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

from Post import Post

