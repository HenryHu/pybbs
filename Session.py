from Config import *
from UserInfo import UserInfo
from Util import Util
import User
from UCache import UCache
import time
import os
import json

class Session:
    def GetID(self):
        return self.sessionid

    def GetUserName(self):
        return self.username

    def GetUser(self):
        return self.user

    @staticmethod
    def GET(svc, session, params, action):
        if (action == 'verify'):
            SessionManager.VerifySession(svc, session, params)
        else:
            print "Session.GET!"
            print params
            svc.send_response(200)
            svc.end_headers()
        return

    @staticmethod
    def POST(svc, session, params, action):
        print "Session.POST!"
        print params
        svc.send_response(200)
        svc.end_headers()
        return

    def __init__(self, user):
        self.username = user.name
        self.uid = UCache.SearchUser(self.username)
        self.sessionid = Util.RandomStr(SESSIONID_LEN)
        self.user = UserManager.LoadUser(user.name)
        self._userinfo = None
        self.utmpent = -1
        SessionManager.Insert(self)

    def Register(self):
        # register this session (so TERM users can see me)
        userinfo = UserInfo()
        userinfo.active = 1
        userinfo.pid = os.getpid()
        if ((self.user.HasPerm(User.PERM_CHATCLOAK) or self.user.HasPerm(User.PERM_CLOAK)) and (self.user.HasFlag(User.CLOAK_FLAG))):
            userinfo.invisible = 1
        userinfo.mode = modes.WWW
        userinfo.pager = 0
        if (self.user.Defined(User.DEF_FRIENDCALL)):
            userinfo.pager |= User.FRIEND_PAGER

        if (self.user.HasFlag(User.PAGER_FLAG)):
            userinfo.pager |= User.ALL_PAGER
            userinfo.pager |= User.FRIEND_PAGER

        if (self.user.Defined(User.DEF_FRIENDMSG)):
            userinfo.pager |= User.FRIEND_PAGER

        if (self.user.Defined(User.DEF_ALLMSG)):
            userinfo.pager |= User.ALL_PAGER
            userinfo.pager |= User.FRIEND_PAGER

        userinfo.uid = self.uid
        userinfo.from = '127.0.0.1' # XXX: fix later
        userinfo.freshtime = int(time.time())
        userinfo.userid = self.username
        userinfo.realname = 'ANONYMOUS' # XXX: fix later
        userinfo.username = self.user.userec.username

        self.utempent = Utmp.GetNewUtmpEntry(userinfo)
        if (self.utempent = -1):
            return None

        userinfo.SetIndex(self.utmpent)
        self.user.GetFriends(userinfo)
        userinfo.save()

        self._userinfo = userinfo
        return userinfo

class SessionManager:
    sessions = {}

    @staticmethod
    def Insert(session):
        SessionManager.sessions[session.sessionid] = session

    @staticmethod
    def GetSession(id):
        if (id not in SessionManager.sessions):
            return None
        return SessionManager.sessions[id]

    @staticmethod
    def VerifySession(svc, session, params):
        if (session == None):
            svc.return_error(404, "session not found or session timed out")
        else:
            svc.send_response(200, 'OK')
            svc.end_headers()
            result = {}
            result['status'] = "ok"
            svc.wfile.write(json.dumps(result))

from UserManager import UserManager
