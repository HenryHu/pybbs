#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
import struct
import Config
from Util import Util
from cstruct import CStruct

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

    def SetRead(self, val):
        return self.SetFlag(0, FILE_READ, val)

    def UpdateDeleteTime(self):
        self.accessed[-1] = int(time.time()) / (3600 * 24) % 100;

    def GetPostTime(self):
        return int(self.filename.split('.')[1])

    def CanBeDeleted(self, user, board):
        return user.IsOwner(self) or user.IsSysop() or board.IsMyBM(user)

    def CanBeEdit(self, user, board):
        return user.IsOwner(self) or user.IsSysop() or board.IsMyBM(user)

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

    def GetInfoExtended(self, user, board, mode = 'post'):
        info = self.GetInfo(mode)
        if self.CanBeDeleted(user, board):
            info['flags'] += ['deletable']
        return info

    def is_anony(self):
        return self.owner != self.realowner
