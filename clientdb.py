import sqlite3
import Config
import os
import datetime
import json
from errors import *

CLIENTS_DB = 'clients.db'

class ClientDB:
    def __init__(self):
        self.conn = sqlite3.connect(os.path.join(Config.BBS_ROOT, CLIENTS_DB), detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.conn.row_factory = sqlite3.Row
        try:
            self.conn.execute("select * from clients")
        except sqlite3.OperationalError:
            self.init_db()

    def find_client(self, client_id):
        c = self.conn.cursor()
        for row in c.execute('SELECT * FROM clients WHERE id=?', (client_id,)):
            return ClientInfo(**row)
        return None

    def list_clients_by_user(self, uid):
        c = self.conn.cursor()
        clients = []
        for row in c.execute('SELECT * FROM clients WHERE user=?', (uid,)):
            clients.append(ClientInfo(**row))
        return clients

    def new_client(self, client):
        if not self.find_client(client.id) is None:
            return self.update_client(client)
        response_types = ','.join(client.response_type)
        grant_types = ','.join(client.grant_type)
        redirect_uris = ','.join(client.redirect_uri)
        scopes = ','.join(client.scopes)
        self.conn.execute("insert into clients values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (client.id, client.secret, client.name, client.user, client.description, redirect_uris, client.created, client.type, client.website, client.logo, response_types, grant_types, client.extra_info, scopes))
        self.conn.commit()

    def update_client(self, client):
        response_types = ','.join(client.response_type)
        grant_types = ','.join(client.grant_type)
        redirect_uris = ','.join(client.redirect_uri)
        scopes = ','.join(client.scopes)
        self.conn.execute("update clients set secret=?, name=?, user=?, description=?, redirect_uri=?, created=?, type=?, website=?, logo=?, response_type=?, grant_type=?, extra_info=?, scope=? where id=?", (client.secret, client.name, client.user, client.description, redirect_uris, client.created, client.type, client.website, client.logo, response_types, grant_types, client.extra_info, scopes, client.id))
        self.conn.commit()

    def remove_client(self, client_id):
        if not client_id:
            return
        self.conn.execute("delete from clients where id = ?", (client_id,))
        self.conn.commit()

    def init_db(self):
        self.conn.execute("create table clients(id text, secret text, name text, user int, description text, redirect_uri text, created timestamp, type text, website text, logo text, response_type text, grant_type text, extra_info text, scopes text)")
        self.conn.commit()

    def close(self):
        self.conn.close()


class ClientInfo:
    _valid_scopes = {'bbs' : "Do whatever you can do in the BBS",
            'auth' : "Authenticate that you are a valid user of the BBS"}
    def __init__(self, id, response_type, grant_type, user, secret = '', type = 'public', name = '', description = '', redirect_uri = '', created = None, website = '', logo = '', extra_info = '', scopes = ''):
        if not id:
            raise WrongArgs('client id cannot be empty')
        self.id = id
        self.secret = secret
        if not name:
            self.name = id
        else:
            self.name = name
        self.user = user
        if not description:
            self.description = id
        else:
            self.description = description
        self.redirect_uri = redirect_uri.split(',')
        if not created:
            self.created = datetime.datetime.now()
        else:
            self.created = created
        self.type = type
        self.website = website
        self.logo = logo
        self.response_type = response_type.split(',')
        self.grant_type = grant_type.split(',')
        self.extra_info = extra_info
        self.scopes = scopes.split(',')

    def check_secret(self, secret):
        return secret == self.secret

    def check_user(self, user):
        return self.user == user

    def check_redirect_uri(self, redirect_uri):
        for allowed_uri in self.redirect_uri:
            if allowed_uri == redirect_uri:
                return True
        return False

    def check_response_type(self, response_type):
        for allowed_type in self.response_type:
            if allowed_type == response_type:
                return True
        return False

    def check_grant_type(self, grant_type):
        for allowed_type in self.grant_type:
            if allowed_type == grant_type:
                return True
        return False

    def add_grant_type(self, grant_type):
        self.grant_type.append(grant_type)

    def add_response_type(self, response_type):
        self.response_type.append(response_type)

    def get_logo(self):
        if self.logo:
            return self.logo
        else:
            return "/res/defappicon.png"

    def get_website(self):
        if self.website:
            return self.website
        else:
            return "http://www.google.com/search?q=%s" % self.name

    def get_default_redirect_uri(self):
        return self.redirect_uri[0]

    def info(self):
        info = {}
        info['client_id'] = self.id
        info['client_secret'] = self.secret
        info['name'] = self.name
        info['description'] = self.description
        info['redirect_uri'] = self.redirect_uri
        info['type'] = self.type
        info['website'] = self.website
        info['logo'] = self.logo
        info['extra_info'] = self.extra_info
        info['response_type'] = self.response_type
        info['grant_type'] = self.grant_type
        info['scopes'] = self.scopes
        return info

    def check_scope(self, scope):
        return scope in self.scopes

    @staticmethod
    def is_valid_scope(scope):
        return scope in ClientInfo._valid_scopes

    def get_scopes_desc(self, scopes):
        result = ''
        for scope in scopes:
            result += "<li class=\"scope_desc\">%s</li>" % self.get_scope_desc(scope)
        return result

    def get_scope_desc(self, scope):
        if not scope in self_valid_scopes:
            raise WrongArgs("invalid scope: %s" % scope)
        return self._valid_scopes[scope]

class Clients:
    @staticmethod
    def GET(svc, session, params, action):
        if session is None: raise NoPerm("login first")
        if action == 'query':
            client_id = svc.get_str(params, 'client_id')
            Clients.query(svc, session, client_id)
        elif action == 'list':
            Clients.list_clients(svc, session)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def POST(svc, session, params, action):
        if session is None: raise NoPerm("login first")
        if action == "update":
            client_id = svc.get_str(params, 'client_id')
            Clients.update(svc, session, params, client_id)
        elif action == "remove":
            client_id = svc.get_str(params, 'client_id')
            Clients.remove(svc, session, params, client_id)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def query(svc, session, client_id):
        clients = ClientDB()
        try:
            client = clients.find_client(client_id)
            if client is None:
                raise NoPerm("permission denied")
            if not client.check_user(session.uid):
                raise NoPerm("permission denied")
            svc.writedata(json.dumps(client.info()))
        finally:
            clients.close()

    @staticmethod
    def list_clients(svc, session):
        clients = ClientDB()
        try:
            client_list = clients.list_clients_by_user(session.uid)
            result = []
            for client in client_list:
                result.append(client.info())
            svc.writedata(json.dumps({'clients': result}))
        finally:
            clients.close()

    @staticmethod
    def update(svc, session, params, client_id):
        clients = ClientDB()
        try:
            client = clients.find_client(client_id)
            client_secret = svc.get_str(params, 'client_secret')
            name = svc.get_str(params, 'name', client_id)
            description = svc.get_str(params, 'description', client_id)
            redirect_uri = svc.get_str(params, 'redirect_uri', '')
            type = svc.get_str(params, 'type', 'public')
            website = svc.get_str(params, 'website', '')
            logo = svc.get_str(params, 'logo', '')
            extra_info = svc.get_str(params, 'extra_info', '')
            response_type = svc.get_str(params, 'response_type', '')
            grant_type = svc.get_str(params, 'grant_type', '')
            scopes = svc.get_str(params, 'scopes', '').split(',')
            for scope in scopes:
                if not ClientInfo.is_valid_scope(scope):
                    raise WrongArgs("illegal scope: %s" % scope)
            if client is not None:
                if not client.check_user(session.uid):
                    raise NoPerm("permission denied")
                client.response_type = response_type.split(',')
                client.grant_type = grant_type.split(',')
            else:
                client = ClientInfo(client_id, response_type, grant_type, session.uid)
            client.secret = client_secret
            client.name = name
            client.description = description
            client.redirect_uri = redirect_uri.split(',')
            client.type = type
            client.website = website
            client.logo = logo
            client.extra_info = extra_info
            client.scopes = scopes

            clients.new_client(client)
            result = {"result": "ok"}
            svc.writedata(json.dumps(result))
        finally:
            clients.close()

    @staticmethod
    def remove(svc, session, params, client_id):
        clients = ClientDB()
        try:
            client = clients.find_client(client_id)
            if client is None:
                raise NoPerm("permission denied")
            else:
                if not client.check_user(session.uid):
                    raise NoPerm("permission denied")
            clients.remove_client(client_id)
            result = {"result": "ok"}
            svc.writedata(json.dumps(result))
        finally:
            clients.close()

def console():
    Config.Config.LoadConfig()

if __name__ == "__main__":
    console()
