from UserManager import UserManager
from Session import Session
import json
from Util import Util
import Config
import time
import base64
from errors import *
import clientdb

AUTH_CODE_LEN = 8 # bytes
AUTH_CODE_VALID = 600 # seconds, recommended by rfc6749

class AuthRecord:
    def __init__(self, code, sid, time, cid):
        self.code = code
        self.sid = sid
        self.time = time
        self.cid = cid

    def CheckTime(self, time):
        if ((time < self.time) or (time > self.time + AUTH_CODE_VALID)):
            return False
        return True

    def CheckClientID(self, cid):
        return self.cid == cid

class AuthError(Exception):
    def __init__(self, rduri, error):
        self.rduri = rduri
        self.error = error

class Auth:
    sessiondb = {}

    @staticmethod
    def GET(svc, session, params, action):
        try:
            # assume all clients are public,
            # so redirect_uri is REQUIRED
            if (action == 'auth'):
                # rfc6749 4.1.1: authorization request
                # rfc6749 4.2.1: authorization request
                rduri = svc.get_str(params, 'redirect_uri')
                state = svc.get_str(params, 'state', '')
                try:
                    resptype = svc.get_str(params, 'response_type')
                    cid = svc.get_str(params, 'client_id')
                except WrongArgs:
                    raise AuthError(rduri, 'invalid_request')

                Auth.Auth(svc, params, rduri, resptype, cid, state)
                return
            elif (action == 'token'):
                # rfc6749 4.1.3: access token request
                # rfc6749 4.1.4: access token response
                # rfc6749 4.3: 'password' method is disabled: insecure
                # rfc6749 4.4: 'client_credentials' method is disabled: impossible
                rduri = svc.get_str(params, 'redirect_uri')
                try:
                    type = svc.get_str(params, 'grant_type')
                    cid = svc.get_str(params, 'client_id')
                    csec = svc.get_str(params, 'client_secret')
                except WrongArgs:
                    raise AuthError(rduri, 'invalid_request')
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
        except AuthError as e:
            Auth.Error(svc, e.rduri, e.error)

    @staticmethod
    def POST(svc, session, params, action):
        try:
            if (action == 'authpage'):
                # rfc6749 4.1.2: authorization response
                # rfc6749 4.2.2: authorization response
                rduri = svc.get_str(params, 'redirect_uri')
                try:
                    cid = svc.get_str(params, 'client_id')
                    name = svc.get_str(params, 'name')
                    pw = svc.get_str(params, 'pass')
                    resptype = svc.get_str(params, 'response_type')
                except WrongArgs:
                    raise AuthError(rduri, 'invalid_request')
                state = svc.get_str(params, 'state', '')
                Auth.AuthPage(svc, rduri, cid, name, pw, state, resptype)
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
                    session.RecordLogin(True)
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
            elif (action == 'token'):
                return Auth.GET(svc, session, params, action)
            else:
                raise WrongArgs("unknown action")
        except AuthError as e:
            Auth.Error(svc, e.rduri, e.error)

    @staticmethod
    def Error(svc, rduri, error):
        svc.send_response(302)
        svc.send_header('Location', rduri + '?error=%s' % error)
        svc.send_header('Content-Length', 0)
        svc.end_headers()
        return

    @staticmethod
    def Auth(svc, params, rduri, resptype, cid, state):
        clients = clientdb.ClientDB()
        try:
            # check client_id valid
            client = clients.find_client(cid)
            if client is None:
                raise AuthError(rduri, 'invalid_client')
            # check client_id may use response_type
            if not client.check_response_type(resptype):
                raise AuthError(rduri, 'invalid_client')
            # check redirect_uri match client_id
            if not client.check_redirect_uri(rduri):
                raise AuthError(rduri, 'invalid_client')
            if resptype == "code" or resptype == "token":
                fauthpage = open(Config.Config.GetString("BBS_DATASVC_ROOT", "") + "authpage.html", "r")
                authpage = fauthpage.read()
                fauthpage.close()
                authpage = authpage % (rduri, cid, state, resptype)
                svc.writedata(authpage)
            else:
                raise AuthError(rduri, 'unsupported_response_type')
        finally:
            clients.close()

    @staticmethod
    def AuthPage(svc, rduri, cid, name, pw, state, resptype):
        clients = clientdb.ClientDB()
        try:
            # check client_id valid
            client = clients.find_client(cid)
            if client is None:
                raise AuthError(rduri, 'invalid_client')
            # check client_id may use response_type
            if not client.check_response_type(resptype):
                raise AuthError(rduri, 'invalid_client')
            # check redirect_uri match client_id
            if not client.check_redirect_uri(rduri):
                raise AuthError(rduri, 'invalid_client')
            user = UserManager.LoadUser(name)
            if (user == None):
                raise AuthError(rduri, 'access_denied')

            if (user.Authorize(pw)):
                session = Session(user, svc.client_address[0])
                session.RecordLogin(True)
                if resptype == "code":
                    # give session, so other info may be recorded
                    code = Auth.RecordSession(session, cid)
                    target_uri = "%s?code=%s" % (rduri, code)
                    if state:
                        target_uri += "&state=%s" % state

                elif resptype == "token":
                    token = session.GetID()
                    # TODO: return expires_in

                    target_uri = "%s?access_token=%s&token_type=session" % (rduri, token)
                    if state:
                        target_uri += "&state=%s" % state
                else:
                    raise AuthError(rduri, 'unsupported_response_type')

                svc.send_response(302)
                svc.send_header('Location', target_uri)
                svc.send_header('Content-Length', 0)
                svc.end_headers()
            else:
                raise AuthError(rduri, 'access_denied')
        finally:
            clients.close()

    @staticmethod
    def GetToken(svc, params, rduri, type, cid, csec):
        clients = clientdb.ClientDB()
        try:
            # check client_id valid // invalid_client
            client = clients.find_client(cid)
            if client is None:
                raise AuthError(rduri, 'invalid_client')
            # check client_id may use grant_type // unauthorized_client
            if not client.check_grant_type(type):
                raise AuthError(rduri, 'unauthorized_client')
            # check client_secret match client_id // invalid_client
            if not client.check_secret(csec):
                raise AuthError(rduri, 'invalid_client')
            # check redirect_uri match client_id // invalid_client
            if not client.check_redirect_uri(rduri):
                raise AuthError(rduri, 'invalid_client')
            if (type != 'authorization_code'):
                raise AuthError(rduri, 'unsupported_grant_type')
            if (not params.has_key('code')):
                raise AuthError(rduri, 'invalid_grant')
            code = params['code']
            sessid = Auth.SessionIDFromCode(code, cid)
            if (sessid == None):
                raise AuthError(rduri, 'invalid_grant')
            Auth.RemoveCode(code)
            resp = {}
            # TODO: expires_in
            # TODO: scope
            resp['access_token'] = sessid
            resp['token_type'] = 'session'

            svc.writedata(json.dumps(resp))
            return
        finally:
            clients.close()

    @staticmethod
    def DisplayCode(svc, code):
        fdcode = open(Config.Config.GetString("BBS_DATASVC_ROOT", "") + "displaycode.html", "r")
        dcode = fdcode.read()
        fdcode.close()
        svc.writedata(dcode % code)
        return

    @staticmethod
    def RecordSession(session, cid):
        code = Util.RandomInt(AUTH_CODE_LEN)
        while (Auth.sessiondb.has_key(code)):
            code = Util.RandomInt(AUTH_CODE_LEN)

        authrec = AuthRecord(code, session.GetID(), time.time(), cid)
        Auth.sessiondb[code] = authrec
        return code

    @staticmethod
    def SessionIDFromCode(code, cid):
        if (Auth.sessiondb.has_key(code)):
            authrec = Auth.sessiondb[code]
            if (authrec.CheckTime(time.time())):
                if authrec.CheckClientID(cid):
                    return authrec.sid
                else:
                    return None
            else:
                return None
        else:
            return None # FIXME: shall we distinguish these two errors?

    @staticmethod
    def RemoveCode(code):
        if (Auth.sessiondb.has_key(code)):
            del Auth.sessiondb[code]

