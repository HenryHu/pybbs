#!/usr/bin/env python

import json
import hashlib
import Config
import Defs

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

    def GetFriends(self, userinfo, session):
        userinfo.friendsnum = 0
        path = self.MyFile("friends")
        numFriends = Util.GetRecordCount(path, Friend.size)
        if (numFriends <= 0):
            return 0
        if (numFriends > Config.MAXFRIENDS):
            numFriends = Config.MAXFRIENDS

        friends = map(Friend, Util.GetRecords(path, Friend.size, 1, numFriends))
        for i in range(numFriends):
            if (User.InvalidId(friends[i].id) or UCache.SearchUser(friends[i].id) == 0):
                friends[i] = friends[numFriends - 1]
                numFriends = numFriends - 1
                friends.pop()

        friends.sort(key = Friend.NCaseId)

        session.topfriend = []
        for i in range(numFriends):
            userinfo.friends_uid[i] = UserManager.SearchUser(friends[i].id)
            session.topfriend.append(friends[i].exp)

        userinfo.friendsnum = numFriends
        return 0

from UserManager import UserManager
