from UserManager import UserManager
from Session import Session
import json
from Util import Util
import Config
import time
import base64
from errors import *
import clientdb
import sqlite3
import os
import datetime
import string

AUTH_CODE_LEN = 8 # bytes
AUTH_CODE_VALID = 600 # seconds, recommended by rfc6749

class AuthRecord:
    def __init__(self, code, sid, time, cid, uid, scopes):
        self.code = code
        self.sid = sid
        self.time = time
        self.cid = cid
        self.uid = uid
        self.scopes = scopes

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

class AuthClientError(Exception):
    pass

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
                cid = svc.get_str(params, 'client_id')
                rduri = svc.get_str(params, 'redirect_uri', '')
                state = svc.get_str(params, 'state', '')
                resptype = svc.get_str(params, 'response_type', '')
                scope = svc.get_str(params, 'scope', 'bbs')

                Auth.Auth(svc, params, rduri, resptype, cid, state, scope)
                return
            elif (action == 'token'):
                # rfc6749 4.1.3: access token request
                # rfc6749 4.1.4: access token response
                # rfc6749 4.3: 'password' method is disabled: insecure
                # rfc6749 4.4: 'client_credentials' method is disabled: impossible
                cid = svc.get_str(params, 'client_id')
                csec = svc.get_str(params, 'client_secret')
                rduri = svc.get_str(params, 'redirect_uri', '')
                type = svc.get_str(params, 'grant_type', '')
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
        except AuthClientError:
            Auth.ClientError(svc)

    @staticmethod
    def POST(svc, session, params, action):
        try:
            if (action == 'authpage'):
                # rfc6749 4.1.2: authorization response
                # rfc6749 4.2.2: authorization response
                cid = svc.get_str(params, 'client_id')
                rduri = svc.get_str(params, 'redirect_uri')
                name = svc.get_str(params, 'name')
                pw = svc.get_str(params, 'pass')
                resptype = svc.get_str(params, 'response_type')
                state = svc.get_str(params, 'state', '')
                scope = svc.get_str(params, 'scope', '')
                Auth.AuthPage(svc, rduri, cid, name, pw, state, resptype, scope)
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
                    (sessid, uid) = Auth.SessionInfoFromCode(code)
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
        except AuthClientError:
            Auth.ClientError(svc)

    @staticmethod
    def Error(svc, rduri, error):
        svc.send_response(302)
        svc.send_header('Location', rduri + '?error=%s' % error)
        svc.send_header('Content-Length', 0)
        svc.end_headers()
        return

    @staticmethod
    def ClientError(svc):
        svc.writedata("<h1>invalid client</h1>client_id error or redirect_uri mismatch", 'text/html', 400)

    @staticmethod
    def Auth(svc, params, rduri, resptype, cid, state, scope):
        clients = clientdb.ClientDB()
        try:
            # check client_id valid
            client = clients.find_client(cid)
            if client is None:
                raise AuthClientError()
            if not rduri:
                rduri = client.get_default_redirect_uri()
            else:
                # check redirect_uri match client_id
                if not client.check_redirect_uri(rduri):
                    raise AuthClientError()
            if not resptype:
                raise AuthError(rduri, 'invalid_request')
            scopes = scope.split(' ')
            for one_scope in scopes:
                if not client.check_scope(one_scope):
                    raise AuthError(rduri, 'invalid_scope')
            # check client_id may use response_type
            if not client.check_response_type(resptype):
                raise AuthError(rduri, 'invalid_client')
            if resptype == "code" or resptype == "token":
                fauthpage = open(Config.Config.GetString("BBS_DATASVC_ROOT", "") + "authpage.html", "r")
                authpage_file = fauthpage.read()
                fauthpage.close()
                authpage_t = string.Template(authpage_file)
                authpage = authpage_t.substitute(redirect_uri=rduri,
                        client_id=cid, state=state, response_type=resptype,
                        name=client.name, website=client.get_website(), logo=client.get_logo(),
                        description=client.description, scope=scope, scope_desc=client.get_scopes_desc(scopes))
                svc.writedata(authpage)
            else:
                raise AuthError(rduri, 'unsupported_response_type')
        finally:
            clients.close()

    @staticmethod
    def AuthPage(svc, rduri, cid, name, pw, state, resptype, scope):
        clients = clientdb.ClientDB()
        try:
            # check client_id valid
            client = clients.find_client(cid)
            if client is None:
                raise AuthClientError()
            # check redirect_uri match client_id
            if not client.check_redirect_uri(rduri):
                raise AuthClientError()
            # check client_id may use response_type
            if not client.check_response_type(resptype):
                raise AuthError(rduri, 'invalid_client')
            user = UserManager.LoadUser(name)
            if (user == None):
                raise AuthError(rduri, 'access_denied')

            scopes = scope.split(' ')
            for one_scope in scopes:
                if not client.check_scope(one_scope):
                    raise AuthError(rduri, 'invalid_scope')

            if (user.Authorize(pw)):
                session = Session(user, svc.client_address[0], scopes = scopes)
                session.RecordLogin(True)
                if resptype == "code":
                    # give session, so other info may be recorded
                    code = Auth.RecordSession(session, cid)
                    target_uri = "%s?code=%s" % (rduri, code)
                    if state:
                        target_uri += "&state=%s" % state

                elif resptype == "token":
                    token = session.GetID()

                    target_uri = "%s?access_token=%s&token_type=session&expires_in=%d" % (rduri, token, Config.SESSION_TIMEOUT_SECONDS)
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
                raise AuthClientError()
            # check client_secret match client_id // invalid_client
            if not client.check_secret(csec):
                raise AuthClientError()
            if not rduri:
                rduri = client.get_default_redirect_uri()
            else:
                # check redirect_uri match client_id // invalid_client
                if not client.check_redirect_uri(rduri):
                    raise AuthClientError()
            if not type:
                raise AuthError(rduri, 'invalid_request')
            # check client_id may use grant_type // unauthorized_client
            if not client.check_grant_type(type):
                raise AuthError(rduri, 'unauthorized_client')
            if type == 'authorization_code':
                if (not params.has_key('code')):
                    raise AuthError(rduri, 'invalid_request')
                code = params['code']
                (sessid, uid, scopes) = Auth.SessionInfoFromCode(code, cid)
                if (sessid == None):
                    raise AuthError(rduri, 'invalid_grant')
                Auth.RemoveCode(code)
            elif type == "refresh_token":
                if not params.has_key('refresh_token'):
                    raise AuthError(rduri, 'invalid_grant')
                old_refresh_token = svc.get_str(params, "refresh_token")
                refreshments = RefreshTokens()
                try:
                    old_token = refreshments.find(old_refresh_token)
                    if old_token is None:
                        raise AuthError(rduri, 'invalid_grant')
                    if old_token['client_id'] != cid:
                        raise AuthError(rduri, 'invalid_grant')
                    uid = old_token['uid']
                    scopes = old_token['scopes']
                    user = UserManager.LoadUserByUid(uid)

                    session = Session(user, svc.client_address[0], scopes = scopes.split(','))
                    session.RecordLogin(True)
                    sessid = session.GetID()

                    refreshments.remove(old_refresh_token)
                finally:
                    refreshments.close()
            else:
                raise AuthError(rduri, 'unsupported_grant_type')

            resp = {}
            # TODO: scope
            resp['access_token'] = sessid
            resp['token_type'] = 'session'
            resp['expires_in'] = Config.SESSION_TIMEOUT_SECONDS

            if client.check_grant_type('refresh_token'):
                refreshments = RefreshTokens()
                try:
                    refresh_token = refreshments.new(uid, cid, svc.client_address[0], scopes)
                finally:
                    refreshments.close()

                resp['refresh_token'] = refresh_token

            svc.writedata(json.dumps(resp))
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

        authrec = AuthRecord(code, session.GetID(), time.time(), cid, session.uid, session.GetScopesStr())
        Auth.sessiondb[code] = authrec
        return code

    @staticmethod
    def SessionInfoFromCode(code, cid):
        if (Auth.sessiondb.has_key(code)):
            authrec = Auth.sessiondb[code]
            if (authrec.CheckTime(time.time())):
                if authrec.CheckClientID(cid):
                    return (authrec.sid, authrec.uid, authrec.scopes)
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

class RefreshTokens:
    def __init__(self):
        self.conn = sqlite3.connect(os.path.join(Config.BBS_ROOT, "auth.db"),
                detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("select * from refreshments")
        except sqlite3.OperationalError:
            self.init_db()

    def init_db(self):
        self.conn.execute("create table refreshments(id text, uid int, created timestamp, client_id text, create_ip text, last_use timestamp, last_ip text, scopes text)")
        self.conn.commit()

    def generate(self):
        return Util.RandomStr(Config.REFRESH_TOKEN_LEN)

    def new(self, uid, client_id, ip, scopes):
        id = self.generate()
        self.conn.execute("insert into refreshments values (?, ?, ?, ?, ?, ?, ?, ?)", (id, uid, datetime.datetime.now(), client_id, ip, datetime.datetime.now(), ip, scopes))
        self.conn.commit()
        return id

    def update(self, id, ip):
        self.conn.execute("update refreshments set last_use = ?, last_ip = ? where id = ?", (datetime.datetime.now(), ip, id))
        self.conn.commit()

    def remove(self, id):
        self.conn.execute("delete from refreshments where id = ?", (id, ))
        self.conn.commit()

    def find(self, id):
        for row in self.conn.execute("select * from refreshments where id = ?", (id, )):
            return row
        return None

    def close(self):
        self.conn.close()


