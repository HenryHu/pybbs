#!/usr/bin/env python
# vim: set fileencoding=utf-8 : 
from Util import Util
import Config
import struct
import json
import base64
from BCache import *
import User
from BRead import BReadMgr
from Error import *
from Log import Log

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
FILE_ON_TOP		= 0x2 = #/* on top mode */
FILE_VOTE		= 0x4 = #/* article with votes */

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

class PostEntry:
    parser = struct.Struct('%dsIII44sH2s%ds%ds%dsIIII%dsI12s' % (Config.FILENAME_LEN, Config.OWNER_LEN, Config.OWNER_LEN, (34 - Config.OWNER_LEN), Config.STRLEN))
    _fields = [['filename', 1], 'id', 'groupid','reid', 'unsued1',
            'attachflag', 'innflag', ['owner',1, Config.OWNER_LEN], ['realowner', 1, Config.OWNER_LEN],
            'unsued2', 'rootcrc', 'eff_size', 'posttime', 'attachment',
            ['title',1, Config.ARTICLE_TITLE_LEN], 'level', 'accessed']

    size = parser.size

    def unpack(self, data):
        Util.Unpack(self, PostEntry.parser.unpack(data))

    def pack(self):
        return PostEntry.parser.pack(Util.Pack(self))

    def __init__(self, data = None):
        if (data == None):
            Util.InitStruct(self)
        else:
            self.unpack(data)

    def IsRootPostAnonymous(self):
        return bool(self.accessed[1] & FILE_ROOTANON)

    def SetRootPostAnonymous(self, rootanon):
        if (rootanon):
            self.accessed[1] |= FILE_ROOTANON
        else:
            self.accessed[1] &= ~FILE_ROOTANON

class Board:

    def __init__(self, bh, bs, idx):
        self.header = bh
        self.status = bs
        self.name = bh.filename
        self.index = idx

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None): return
        bo = None
        if (params.has_key('name')):
            name = params['name']
            bo = BoardManager.GetBoard(name)
            if (bo == None):
                svc.send_response(404, 'Board not found')
                svc.end_headers()
                return

        if (action == 'post_list'):
            if (bo == None):
                svc.send_response(400, 'Lack of board name')
                svc.end_headers()
                return
            if (bo.CheckReadPerm(session.GetUser())):
                bo.GetPostList(svc, session, params)
            else:
                svc.send_response(403, 'Permission denied')
                svc.end_headers()
                return
        elif (action == 'list'):
            BoardManager.ListBoards(svc, session, params)
        else:
            svc.return_error(400, 'Unknown action')
        return

    @staticmethod
    def POST(svc, session, params, action):
        svc.return_error(400, 'Unknown action')
        return

    def GetBoardPath(self):
        return Config.BBS_ROOT + 'boards/%s/' % self.name

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
        print start, '   ', end
        if ((start <= end) and (start >= 1) and (end <= self.status.total)):
            bread = BReadMgr.LoadBRead(session.GetUser().name)
            if (bread != None):
                bread.Load(self.name)
            if (mode == 'normal'):
                svc.send_response(200, 'OK %d %d' % (start, end))
                svc.end_headers()
                dirf = open(self.GetDirPath(mode), 'rb')
                post = {}
                first = True
                svc.wfile.write('[\n');
                for i in range(start - 1, end):
                    if (not first):
                        svc.wfile.write(',\n')
                    first = False
                    pe = self.GetPostEntry(i, mode, dirf)
                    post['id'] = i + 1
                    post['title'] = Util.gbkDec(pe.title)
                    post['attachflag'] = pe.attachflag
                    post['attachment'] = pe.attachment
                    post['owner'] = Util.gbkDec(pe.owner) # maybe...
                    post['posttime'] = int(pe.filename.split('.')[1])
                    read = True
                    if (bread != None):
                        read = not bread.QueryUnread(pe.id, self.name)
                    post['read'] = read
#                    post['filename'] = pe.filename
                    svc.wfile.write(json.dumps(post, 'utf-8'))
                svc.wfile.write('\n]')
                dirf.close()
        else:
            svc.send_response(416, 'Out of range')
            svc.end_headers()
            
        return

    def GetPostEntry(self, postid, mode = 'normal', fd = None):
        pe = None
        if (fd == None):
            dirf = open(self.GetDirPath(mode), 'rb')
            dirf.seek(postid * PostEntry.size)
            pe = PostEntry(dirf.read(PostEntry.size))
            dirf.close()
        else:
            fd.seek(postid * PostEntry.size)
            pe = PostEntry(fd.read(PostEntry.size))
        return pe

    def GetPost(self, svc, session, params, id):
        mode = Util.GetString(params, 'mode', 'normal')
        self.UpdateBoardInfo()
        if ((id >= 1) and (id <= self.status.total)):
            pe = None
            pe = self.GetPostEntry(id - 1, mode)
            postf = open(self.GetBoardPath() + pe.filename, 'rb')
            if (postf != None):
                svc.send_response(200, 'OK')
                svc.end_headers()
                post = {}
                post['id'] = id
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
                svc.wfile.write(json.dumps(post))
                postf.close()
                bread = BReadMgr.LoadBRead(session.GetUser().name)
                bread.Load(self.name)
                bread.MarkRead(pe.id, self.name)
            else:
                svc.send_response(500, 'Error: load failed ')
                svc.end_headers()
        else:
            svc.send_response(416, 'Out of range')
            svc.end_headers()

        return

    def GetNextPostReq(self, svc, session, params, id):
        direction = Util.GetString(params, 'direction', 'forward')
        bfwd = True
        if (direction == 'backward'):
            bfwd = False
        next_id = self.GetNextPost(id, bfwd)
        if (next_id == ERROR_OUT_OF_RANGE):
            svc.send_response(416, 'Out of range')
            svc.end_headers()
        elif next_id == ERROR_OPEN_FAIL:
            svc.send_response(500, 'Load failed')
            svc.end_headers()
        elif next_id == ERROR_NOT_FOUND:
            svc.send_response(404, 'Not found')
            svc.end_headers()
        elif next_id < 1:
            svc.send_response(500, 'unknown error')
            svc.end_headers()
        else:
            svc.send_response(200)
            svc.end_headers()
            nextinfo = {}
            nextinfo['nextid'] = next_id
            svc.wfile.write(json.dumps(nextinfo))
        
    def GetNextPost(self, id, forward):
        self.UpdateBoardInfo()
        if ((id >= 1) and (id <= self.status.total)):
            dirf = open(self.GetDirPath("normal"), 'rb')
            if (dirf == None):
                return ERROR_OPEN_FAIL
            pe = self.GetPostEntry(id - 1, "normal", dirf)
            if (forward):
                i = id + 1
            else:
                i = id - 1
            while ((i >= 1) and (i <= self.status.total)):
                pxe = self.GetPostEntry(i - 1, "normal", dirf)
                if (pxe.groupid == pe.groupid):
                    dirf.close()
                    return i
                if (forward):
                    i = i + 1
                else:
                    i = i - 1
            dirf.close()
            return ERROR_NOT_FOUND
        else:
            return ERROR_OUT_OF_RANGE

    def GetAttachmentReq(self, svc, session, params, id):
        mode = Util.GetString(params, 'mode', 'normal')
        offset = Util.GetInt(params, 'offset')
        if (offset <= 0):
            svc.send_response(400, 'invalid or lack offset')
            svc.end_headers()
            return
        self.UpdateBoardInfo()
        if ((id >= 1) and (id <= self.status.total)):
            pe = self.GetPostEntry(id - 1, mode)
            attach = Post.ReadAttachment(self.GetBoardPath() + pe.filename, offset)
            attach = {'name' : attach[0], 'content' : base64.b64encode(attach[1])}
            svc.send_response(200, 'OK')
            svc.end_headers()
            svc.wfile.write(json.dumps(attach))
        else:
            svc.send_response(416, 'Out of range')
            svc.end_headers()

        return

    def UpdateBoardInfo(self):
        self.status.unpack()
        return

    def GetInfo(self):
        rboard = {}
        rboard['name'] = self.name
        rboard['id'] = self.index
        rboard['BM'] = self.GetBM()
        rboard['total'] = self.GetTotal()
        rboard['currentusers'] = self.GetCurrentUsers()
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

    def GetBM(self):
        return self.header.BM

    def GetTotal(self):
        return self.status.total

    def GetCurrentUsers(self):
        return self.status.currentusers

    def GetLastPost(self):
        return self.status.lastpost

    def GetUnread(self, user):
        bread = BReadMgr.LoadBRead(user)
        if (bread == None):
            return True
        else:
            succ = bread.Load(self.name)
            if (not succ):
                return True
            return bread.QueryUnread(self.GetLastPost(), self.name)

    def CheckReadonly(self):
        return self.CheckFlag(BOARD_READONLY)

    def CanAnonyPost(self):
        return self.CheckFlag(BOARD_ANNONY)

    def CanAnonyReply(self):
        return self.CheckFlag(BOARD_ANONYREPLY)

    def IsJunkBoard(self):
        return self.CheckFlag(BOARD_JUNK)

    def PostArticle(self, user, title, content, refile, signature_id, anony):
        mycrc = binascii.crc32(user.name)
        if (self.CheckReadonly()):
            return False

        if (not self.CheckPostPerm(user)):
            return False

        if (self.DeniedUser(user)):
            if (not user.HasPerm(User.PERM_SYSOP)):
                return False

        while (title[:4] == "Re: "):
            title = title[4:]

        may_anony = False
        if (refile == None): # not in reply mode
            if (self.name == "Announce"):
                may_anony = True
            elif (self.CanAnonyPost()):
                may_anony = True
        else:
            if (self.CanAnonyPost() and mycrc == refile.rootcrc):
                may_anony = True
            else:
                if (self.CanAnonyReply()):
                    may_anony = True

        if (not may_anony):
            anony = False

        if (signature_id < 0):
            Log.error("random signature: not implemented")
            return

        title = title.replace('\033', ' ')

        post_file = PostEntry()
        post_file.filename = self.GetPostFilename()
        if (anony):
            post_file.owner = user.name
        else:
            post_file.owner = self.name
        post_file.realowner = user.name
        content_encoded = content.encode('gbk')
        post_file.eff_size = len(content_encoded)

        if (refile != None):
            post_file.rootcrc = refile.rootcrc
            if (refile.IsRootPostAnonymous()):
                post_file.SetRootPostAnonymous(True)
        else:
            post_file.rootcrc = mycrc
            if (anony):
                post_file.SetRootPostAnonymous(True)

        post_file.title = title
        # TODO: outpost ('SS')
        post_file.innflag = 'LL'

        self.AfterPost(post_file)

        if (not self.IsJunkBoard()):
            user.AddNumPosts()

        return

    def AfterPost(self, post_file):
        pass

from Post import Post
from BoardManager import BoardManager

