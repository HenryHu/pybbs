from Config import *
from Util import Util
import json

class Session:
    sessionid = ''
    username = ''
    user = None

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
        self.sessionid = Util.RandomStr(SESSIONID_LEN)
        self.user = UserManager.LoadUser(user.name)
        SessionManager.Insert(self)

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
            svc.return_error(404, "session not found or timeout")
        else:
            svc.send_response(200, 'OK')
            svc.end_headers()
            result = {}
            result['status'] = "ok"
            svc.wfile.write(json.dumps(result))

from UserManager import UserManager
