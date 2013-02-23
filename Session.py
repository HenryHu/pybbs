from Config import *
from UserInfo import UserInfo
from Util import Util
import Utmp
import modes
import User
from UCache import UCache
import time
import os
import json
import sqlite3
import datetime
from Log import Log
from errors import *

class Session:
    def GetID(self):
        return self.sessionid

    def GetUserName(self):
        return self.username

    def GetUser(self):
        return self.user

    def Timeout(self):
        return (datetime.datetime.now() - self.created > SESSION_TIMEOUT)

    @staticmethod
    def GET(svc, session, params, action):
        if (action == 'verify'):
            SessionManager.VerifySession(svc, session, params)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def POST(svc, session, params, action):
        raise WrongArgs("unknown action")

    def __init__(self, user, fromip, _sessionid = None, _created = None, scopes = ['auth']):
        self.username = user.name
        self.uid = UCache.SearchUser(self.username)
        if (_sessionid is None):
            self.sessionid = Util.RandomStr(SESSIONID_LEN)
            self.created = datetime.datetime.now()
        else:
            self.sessionid = _sessionid
            self.created = _created
        self.user = UserManager.LoadUser(user.name)
        self._userinfo = None
        self.utmpent = -1
        self._fromip = fromip
        self.scopes = scopes
        SessionManager.Insert(self)
        if (_sessionid is None):
            SessionManager.Record(self)
        else:
            SessionManager.Update(self)

    def InitNewUserInfo(self):
        userinfo = UserInfo()
        userinfo.active = 1
        userinfo.pid = os.getpid()
        if ((self.user.HasPerm(User.PERM_CHATCLOAK) or self.user.HasPerm(User.PERM_CLOAK)) and (self.user.HasFlag(User.CLOAK_FLAG))):
            userinfo.invisible = 1
        userinfo.mode = modes.XMPP
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
        self.utmpent = Utmp.Utmp.GetNewUtmpEntry(userinfo)
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
        Utmp.Utmp.Clear(self.utmpent, self.uid, self._userinfo.pid)
        return True

    def RecordLogin(self, count = False):
        self.user.RecordLogin(self._fromip, self._userinfo, count)

    def GetMirror(self, port = 0):
        server = Config.GetString("BBS_WEBDOMAIN", "")
        if (not server):
            server = Config.GetString("BBSDOMAIN", "")
        if (not server):
            raise ServerError("can't get server domain")
        return server

    def CheckScope(self, scope):
        return scope in self.scopes

    def GetScopesStr(self):
        return ','.join(self.scopes)

class SessionManager:
    sessions = {}

    @staticmethod
    def Insert(session):
        SessionManager.sessions[session.sessionid] = session

    @staticmethod
    def Record(session):
        conn = SessionManager.ConnectDB()

        now = datetime.datetime.now()
        conn.execute("insert into sessions values (?, ?, ?, ?, ?, ?, ?)", (session.sessionid, session.username, now, now, session._fromip, session._fromip, session.GetScopesStr()))

        conn.commit()
        conn.close()

    @staticmethod
    def Update(session):
        conn = SessionManager.ConnectDB()

        now = datetime.datetime.now()
        conn.execute("update sessions set last_seen = ?, last_ip = ? where id = ?", (now, session._fromip, session.sessionid))
        conn.commit()
        conn.close()

    @staticmethod
    def ConnectDB():
        conn = sqlite3.connect(BBS_ROOT + "auth.db", detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("select * from sessions")
        except sqlite3.OperationalError:
            SessionManager.InitDB(conn);

        return conn

    @staticmethod
    def InitDB(conn):
        conn.execute("create table sessions(id text, username text, created timestamp, last_seen timestamp, login_ip text, last_ip text, scopes text)")
        conn.commit()

    @staticmethod
    def GetSession(id, fromip):
        now = datetime.datetime.now()
        if (id not in SessionManager.sessions):
            conn = SessionManager.ConnectDB()

            try:
                for row in conn.execute("select * from sessions where id = ?", (id, )):
                    username = row['username']
                    user = UserManager.LoadUser(username)
                    if (user is None):
                        continue
                    created = row['created']
                    scopes = row['scopes'].split(',')
                    session = Session(user, fromip, id, created, scopes)
                    if (session.Timeout()):
                        return None
                    session.RecordLogin()
                    return session
                return None
            finally:
                conn.close()

        session = SessionManager.sessions[id]
        if (session.Timeout()):
            return None
        session._fromip = fromip
        SessionManager.Update(session)
        session.RecordLogin()
        return session

    @staticmethod
    def VerifySession(svc, session, params):
        if (session == None):
            svc.return_error(404, "session not found or session timed out")
        else:
            if not session.CheckScope('bbs') and not session.CheckScope('auth'): raise NoPerm("out of scope")
            result = {}
            result['status'] = "ok"
            svc.writedata(json.dumps(result))

from UserManager import UserManager
