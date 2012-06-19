from UserManager import UserManager
from Session import Session
import json
from Util import Util
import Config
import time
import base64
from errors import *

AUTH_CODE_LEN = 8 # bytes
AUTH_CODE_VALID = 3600 # seconds

class AuthRecord:
    def __init__(self, code, sid, time):
        self.code = code
        self.sid = sid
        self.time = time

    def CheckTime(self, time):
        if ((time < self.time) or (time > self.time + AUTH_CODE_VALID)):
            return False
        return True

class Auth:
    sessiondb = {}

    @staticmethod
    def GET(svc, session, params, action):
        if (action == 'auth'):
            rduri = svc.get_str(params, 'redirect_uri')
            try:
                resptype = svc.get_str(params, 'response_type')
                cid = svc.get_str(params, 'client_id')
            except WrongArgs:
                Auth.Error(svc, rduri, 'invalid_request')
                return

            Auth.Auth(svc, params, rduri, resptype, cid)
            return
        elif (action == 'token'):
            rduri = svc.get_str(params, 'redirect_uri')
            try:
                type = svc.get_str(params, 'grant_type')
                cid = svc.get_str(params, 'client_id')
                csec = svc.get_str(params, 'client_secret')
            except WrongArgs:
                Auth.Error(svc, rduri, 'invalid_request')
                return
            Auth.GetToken(svc, params, rduri, type, cid, csec)
            return
        elif (action == 'displaycode'):
            if (not params.has_key('code')):
                if (params.has_key('error')):
                    svc.writedata("<h1>Error, reason: %s" % params['error'], code = 400)
                    return
                svc.writedata("Please provide auth code to display", code = 400)
                return
            code = params['code']
            Auth.DisplayCode(svc, code)
        else:
            raise WrongArgs('unknown action')

    @staticmethod
    def POST(svc, session, params, action):
        if (action == 'authpage'):
            rduri = svc.get_str(params, 'redirect_uri')
            if (not params.has_key('client_id') or not params.has_key('name') or not params.has_key('pass')):
                Auth.Error(svc, rduri, 'invalid_request')
                return
            cid = params['client_id']
            name = params['name']
            pw = params['pass']
            # todo: check client_id valid
            # todo: check client_id may use response_type
            # todo: check redirect_uri match client_id
            Auth.AuthPage(svc, rduri, cid, name, pw)
        elif (action == 'pwauth'):
            raise NoPerm('pwauth is disabled')
            if (not params.has_key('user') or not params.has_key('pass')):
                raise NoPerm('too few args')
            name = params['user']
            epw = params['pass']
            pw = base64.b64decode(epw)
#            print "name: %s pass: %s" % (name, pw)
            user = UserManager.LoadUser(name)
            if (user == None):
                raise NoPerm('forbidden')

            if (user.Authorize(pw)):
                session = Session(user, svc.client_address[0])
                # give session, so other info may be recorded
                code = Auth.RecordSession(session)
                sessid = Auth.SessionIDFromCode(code)
                resp = {}
                resp['access_token'] = sessid
                resp['token_type'] = 'session'
                svc.writedata(json.dumps(resp))
                return
            else:
                raise NoPerm('forbidden')
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def Error(svc, rduri, error):
        svc.send_response(302)
        svc.send_header('Location', rduri + '?error=%s' % error)
        svc.send_header('Content-Length', 0)
        svc.end_headers()
        return

    @staticmethod
    def Auth(svc, params, rduri, resptype, cid):
        # todo: check client_id valid
        # todo: check client_id may use response_type
        # todo: check redirect_uri match client_id
        if (resptype != "code"):
            Auth.Error(svc, rduri, 'unsupported_response_type')
            return
        fauthpage = open(Config.Config.GetString("BBS_DATASVC_ROOT", "") + "authpage.html", "r")
        authpage = fauthpage.read()
        fauthpage.close()
        authpage = authpage % (rduri, cid)
        svc.writedata(authpage)
        return

    @staticmethod
    def AuthPage(svc, rduri, cid, name, pw):
        user = UserManager.LoadUser(name)
        if (user == None):
            Auth.Error(svc, rduri, 'access_denied')
            return

        if (user.Authorize(pw)):
            session = Session(user, svc.client_address[0])
            # give session, so other info may be recorded
            code = Auth.RecordSession(session)
            svc.send_response(302)
            svc.send_header('Location', rduri + '?code=' + code)
            svc.send_header('Content-Length', 0)
            svc.end_headers()
            return

        else:
            Auth.Error(svc, rduri, 'access_denied')
            return


    @staticmethod
    def GetToken(svc, params, rduri, type, cid, csec):
        # todo: check client_id valid // invalid_client
        # todo: check client_id may use grant_type // unauthorized_client
        # todo: check client_secret match client_id // invalid_client
        # todo: check redirect_uri match client_id // invalid_client
        if (type != 'authorization_code'):
            Auth.Error(svc, rduri, 'unsupported_grant_type')
            return
        if (not params.has_key('code')):
            Auth.Error(svc, rduri, 'invalid_grant')
            return
        code = params['code']
        sessid = Auth.SessionIDFromCode(code)
        if (sessid == None):
            Auth.Error(svc, rduri, 'invalid_grant')
            return
        Auth.RemoveCode(code)
        resp = {}
        resp['access_token'] = sessid
        resp['token_type'] = 'session'

        svc.writedata(json.dumps(resp))
        return

    @staticmethod
    def DisplayCode(svc, code):
        fdcode = open(Config.Config.GetString("BBS_DATASVC_ROOT", "") + "displaycode.html", "r")
        dcode = fdcode.read()
        fdcode.close()
        svc.writedata(dcode % code)
        return

    @staticmethod
    def RecordSession(session):
        code = Util.RandomInt(AUTH_CODE_LEN)
        while (Auth.sessiondb.has_key(code)):
            code = Util.RandomInt(AUTH_CODE_LEN)

        authrec = AuthRecord(code, session.GetID(), time.time())
        Auth.sessiondb[code] = authrec
        return code

    @staticmethod
    def SessionIDFromCode(code):
        if (Auth.sessiondb.has_key(code)):
            authrec = Auth.sessiondb[code]
            if (authrec.CheckTime(time.time())):
                return authrec.sid
            else:
                return None
        else:
            return None # FIXME: shall we distinguish these two errors?

    @staticmethod
    def RemoveCode(code):
        if (Auth.sessiondb.has_key(code)):
            del Auth.sessiondb[code]

