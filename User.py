#!/usr/bin/env python

import json
import hashlib
import Config
import Defs
from Log import Log
from UCache import UCache
from Friend import Friend
from Util import Util

PERM_BASIC = 000001
PERM_CHAT = 000002
PERM_PAGE = 000004
PERM_POST = 000010
PERM_LOGINOK = 000020
PERM_BMAMANGER = 000040
PERM_CLOAK = 000100
PERM_SEECLOAK = 000200
PERM_XEMPT = 000400
PERM_WELCOME = 001000
PERM_BOARDS = 002000
PERM_ACCOUNTS = 004000
PERM_CHATCLOAK = 010000
PERM_DENYRELAX = 020000
PERM_SYSOP = 040000
PERM_POSTMASK = 0100000
PERM_ANNOUNCE = 0200000
PERM_OBOARDS = 0400000
PERM_ACBOARD = 01000000
PERM_NOZAP = 02000000
PERM_CHATOP = 04000000
PERM_ADMIN = 010000000
PERM_HORNOR = 020000000
PERM_SECANC = 040000000
PERM_JURY = 0100000000
PERM_CHECKCD = 0200000000
PERM_SUICIDE = 0400000000
PERM_COLLECTIVE = 01000000000
PERM_DISS = 02000000000
PERM_DENYMAIL = 04000000000
# these are flags in userec.flags[0] 
PAGER_FLAG   = 0x1  # /* true if pager was OFF last session */
CLOAK_FLAG   = 0x2  # /* true if cloak was ON last session */
BRDSORT_FLAG = 0x20 # /* true if the boards sorted alphabetical */
CURSOR_FLAG  = 0x80 # /* true if the cursor mode open */
GIVEUP_FLAG  = 0x4  # /* true if the user is giving up  by bad 2002.7.6 */
PCORP_FLAG	 = 0x40	# /* true if have personalcorp */
#define DEFINE(user,x)     ((x)?((user)->userdefine[def_list(x)])&(x):1)
DEF_ACBOARD    = 000001
DEF_COLOR      = 000002
DEF_EDITMSG    = 000004
DEF_NEWPOST    = 000010
DEF_ENDLINE    = 000020
DEF_LOGFRIEND  = 000040
DEF_FRIENDCALL = 000100
DEF_LOGOUT     = 000200
DEF_INNOTE     = 000400
DEF_OUTNOTE    = 001000
DEF_NOTMSGFRIEND = 002000
DEF_NORMALSCR  = 004000
DEF_CIRCLE     = 010000
DEF_FIRSTNEW   = 020000
DEF_TITLECOLOR = 040000
DEF_ALLMSG     = 0100000
DEF_FRIENDMSG  = 0200000
DEF_SOUNDMSG   = 0400000
DEF_MAILMSG    = 01000000
DEF_LOGININFORM= 02000000
DEF_SHOWSCREEN = 04000000
DEF_SHOWHOT    = 010000000
DEF_NOTEPAD    = 020000000
DEF_IGNOREMSG  = 040000000   #   /* Added by Marco */
DEF_HIGHCOLOR = 0100000000   #/*Leeward 98.01.12 */
DEF_SHOWSTATISTIC = 0200000000 #   /* Haohmaru */
DEF_UNREADMARK = 0400000000    #   /* Luzi 99.01.12 */
DEF_USEGB   = 01000000000   #    /* KCN,99.09.05 */
DEF_CHCHAR  = 02000000000
DEF_SHOWDETAILUSERDATA = 04000000000
DEF_SHOWREALUSERDATA  = 010000000000
DEF_HIDEIP                    = 040000000001

#//DEF_SPLITSCREEN 02000000000 /* bad 2002.9.1 */
ALL_PAGER = 0x1
FRIEND_PAGER = 0x2
ALLMSG_PAGER = 0x4
FRIENDMSG_PAGER = 0x8

class User:
    name = ''
    userec = None

    def __init__(self, user, userec):
        self.name = user
        self.userec = userec

    @staticmethod
    def POST(svc, session, params, action):
        if (action == 'login'):
            ok = False
            if (not (params.has_key('name') and (params.has_key('pass')))):
                svc.send_response(400, 'Lack of username or password')
                svc.end_headers()
                return

            UserManager.HandleLogin(svc, params['name'], params['pass'])
        else:
            svc.return_error(400, 'Unknown action')

    @staticmethod
    def GET(svc, session, params, action):
        svc.return_error(400, 'Unknown action')

    @staticmethod
    def OwnFile(userid, str):
        return "%s/home/%s/%s/%s" % (Config.BBS_ROOT, userid[0].upper(), userid, str)

    def MyFile(self, str):
        return User.OwnFile(self.name, str)

    @staticmethod
    def CacheFile(userid, str):
        return "%s/cache/home/%s/%s/%s" % (Config.BBS_ROOT, userid[0].upper(), userid, str)

    def Authorize(self, password):
        m = hashlib.md5()
        m.update(Defs.PASSMAGIC)
        m.update(password)
        m.update(Defs.PASSMAGIC)
        m.update(self.name)
        ret = m.digest()
        return (ret == self.userec.md5passwd)

    def HasPerm(self, perm):
        if (perm == 0):
            return True
        if (self.userec.userlevel & perm != 0):
            return True
        return False

    def HasFlag(self, flag):
        if (self.userec.flags & flag != 0):
            return True
        return False

    @staticmethod
    def DefinePos(value):
        if (value < DEF_HIDEIP):
            return 0
        return 1

    def Defined(self, value):
        if (value == 0):
            return True
        if (self.userec.userdef[User.DefinePos(value)] & value != 0):
            return True
        return False

    def CanReadClub(self, clubnum):
        idx = clubnum - 1
        if (self.userec.club_read_rights[idx >> 5] & (1 << (idx & 0x1f)) != 0):
            return True
        return False

    def CanPostClub(self, clubnum):
        idx = clubnum - 1
        if (self.userec.club_write_rights[idx >> 5] & (1 << (idx & 0x1f)) != 0):
            return True
        return False

    def GetTitle(self):
        return self.userec.title

    def CanSendTo(self, userid):
        if (self.HasPerm(PERM_SYSOP)):
            return True
        return True

    @staticmethod
    def InvalidId(username):
        if (username.isalpha()):
            return False
        return True

    def GetFriends(self, userinfo):
        userinfo.friendsnum = 0
        path = self.MyFile("friends")
        numFriends = Util.GetRecordCount(path, Friend.size)
#        Log.info("numFriends: %d" % numFriends)
        if (numFriends <= 0):
            return 0
        if (numFriends > Config.MAXFRIENDS):
            numFriends = Config.MAXFRIENDS

        friends = map(Friend, Util.GetRecords(path, Friend.size, 1, numFriends))
        i = 0
        while (True):
            if (i >= numFriends):
                break
#            Log.debug("checking %d %s %d" % (i, friends[i].id, -1 if User.InvalidId(friends[i].id) else UCache.SearchUser(friends[i].id)))
            if (User.InvalidId(friends[i].id) or UCache.SearchUser(friends[i].id) == 0):
#                Log.debug("removing %d %s" % (i, friends[i].id))
                friends[i] = friends[numFriends - 1]
                numFriends = numFriends - 1
                friends.pop()
                i = i - 1
#            print i,numFriends,len(friends)

            i = i + 1

        friends.sort(key = Friend.NCaseId)

        userinfo.friends_nick = []
        for i in range(numFriends):
#            Log.debug("friend %d %s" % (i, friends[i].id))
            userinfo.friends_uid[i] = UCache.SearchUser(friends[i].id)
            userinfo.friends_nick.append(friends[i].exp)

        userinfo.friendsnum = numFriends
        return 0

    @staticmethod
    def RemoveMsgCount(username):
        pass

from UserManager import UserManager
