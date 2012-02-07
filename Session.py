from Config import *
from UserInfo import UserInfo
from Util import Util
from Utmp import Utmp
import modes
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

    def __init__(self, user, fromip):
        self.username = user.name
        self.uid = UCache.SearchUser(self.username)
        self.sessionid = Util.RandomStr(SESSIONID_LEN)
        self.user = UserManager.LoadUser(user.name)
        self._userinfo = None
        self.utmpent = -1
        self._fromip = fromip
        SessionManager.Insert(self)


    def InitNewUserInfo(self):
        userinfo = UserInfo()
        userinfo.active = 1
        userinfo.pid = os.getpid()
        if ((self.user.HasPerm(User.PERM_CHATCLOAK) or self.user.HasPerm(User.PERM_CLOAK)) and (self.user.HasFlag(User.CLOAK_FLAG))):
            userinfo.invisible = 1
        userinfo.mode = modes.TALK
        userinfo.pager = 0
        if (self.user.Defined(User.DEF_FRIENDCALL)):
            userinfo.pager |= User.FRIEND_PAGER

        if (self.user.HasFlag(User.PAGER_FLAG)):
            userinfo.pager |= User.ALL_PAGER
            userinfo.pager |= User.FRIEND_PAGER

        if (self.user.Defined(User.DEF_FRIENDMSG)):
            userinfo.pager |= User.FRIENDMSG_PAGER

        if (self.user.Defined(User.DEF_ALLMSG)):
            userinfo.pager |= User.ALLMSG_PAGER
            userinfo.pager |= User.FRIENDMSG_PAGER

        userinfo.uid = self.uid
        setattr(userinfo, 'from', self._fromip)
        userinfo.freshtime = int(time.time())
        userinfo.userid = self.username
        userinfo.realname = 'ANONYMOUS' # XXX: fix later
        userinfo.username = self.user.userec.username
        return userinfo

    def Register(self):
        # register this session (so TERM users can see me)
        userinfo = self.InitNewUserInfo()
        self.utmpent = Utmp.GetNewUtmpEntry(userinfo)
        if (self.utmpent == -1):
            return None

        self.user.GetFriends(userinfo)
        userinfo.save()

        self._userinfo = userinfo
        return userinfo

    def Unregister(self):
        if (self.utmpent < 0):
            Log.error("Unregister() without Register() or failed!")
            return False
        Utmp.Clear(self.utmpent, self.uid, self._userinfo.pid)
        return True

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
