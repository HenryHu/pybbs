#!/usr/bin/env python

"""Data service
   by henryhu
   2010.12.06    created.
"""

import cgi
import mimetools
import os
import string
import struct
import urlparse
import SocketServer
import socket
import re
import sys
import threading
from pwd import getpwnam
from SocketServer import BaseServer
from BaseHTTPServer import *
#from OpenSSL import SSL
import ssl
from Post import Post
from Board import Board
from Session import Session
from BCache import BCache
from Config import Config
from BoardManager import BoardManager
from User import User
from UCache import UCache
from UserManager import UserManager
from Session import SessionManager
from Auth import Auth
from MsgBox import MsgBox
from FavBoard import FavBoard
from digest import Digest
from Log import Log
import store
import mail
import commondata
import clientdb
import resource
import fast_indexer
from errors import *

class DataService(BaseHTTPRequestHandler):
    classes = {"post"       : Post,
               "board"      : Board,
               "session"    : Session,
               "user"       : User,
               "auth"       : Auth,
               "favboard"   : FavBoard,
               "digest"     : Digest,
               "store"      : store.Store,
               "mail"       : mail.Mail,
               "clients"    : clientdb.Clients,
               "res"        : resource.Resource
              }
    classes_keys = classes.keys()
    protocol_version = 'HTTP/1.1'

    def parse_req(self, req):
        m = re.search("^/([^/]*)/(.*)$", req)
        if (m != None):
            return (m.group(1), m.group(2))
        else:
            raise exception()

    def setup(self):
        self.wbufsize = 16384
        BaseHTTPRequestHandler.setup(self)
#    def setup(self):
#        self.connection = self.request
#        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
#        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

    def address_string(self):
        try:
            ip = self.headers['X-Forwarded-For']
        except KeyError:
            return self.client_address[0]
        return ip

    def writedata(self, data, type = '', code = 200):
        if (self._params):
            if ('jsonp' in self._params):
                jsonp = self._params['jsonp']
                data = '%s(%s);' % (jsonp, data)
            elif ('jsoncallback' in self._params):
                jsonp = self._params['jsoncallback']
                data = '%s(%s);' % (jsonp, data)
        try:
            self.send_response(code)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', len(data))
            if len(type) > 0:
                self.send_header('Content-Type', type)
            else:
                self.send_header('Content-Type', 'text/html; charset=UTF-8')

            self.end_headers()
            self.wfile.write(data)
            self.wfile.flush()
        except:
            pass

    def return_error(self, code, reason, data = ''):
        self.send_response(code, reason)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_POST(self):
        url_tuple = urlparse.urlsplit(self.path)
        params = dict(urlparse.parse_qsl(url_tuple[3]))
        req = url_tuple[2]

        ctype, pdict = cgi.parse_header(self.headers.getheader('content-type'))
        if ctype == 'multipart/form-data':
            postvars = cgi.parse_multipart(self.rfile, pdict)
            for i in postvars:
                postvars[i] = postvars[i][0]
        elif ctype == 'application/x-www-form-urlencoded':
            length = int(self.headers.getheader('content-length'))
            postvars = dict(urlparse.parse_qsl(self.rfile.read(length), keep_blank_values=1))
        else:
            postvars = {}

        params = dict(params.items() + postvars.items())
        session = self.GetSession(params)
        self._params = params

        try:
            cls, op = self.parse_req(req)
        except:
            self.log_error('Bad request: %s', req)
            self.return_error(400, 'bad request')
            return

        if (cls in DataService.classes_keys):
            with error_handler(self):
                DataService.classes[cls].POST(self, session, params, op)
        else:
            self.log_error('Bad POST %s', self.path)
            self.return_error(400, 'bad request')

    def GetSession(self, params):
        if (params.has_key('session')):
            sid = params['session']
            return SessionManager.GetSession(sid, self.client_address[0])
        else:
            return None

    def do_GET(self):
        url_tuple = urlparse.urlsplit(self.path)
        params = dict(cgi.parse_qsl(url_tuple[3]))
        req = url_tuple[2]
        session = self.GetSession(params)
        self._params = params

        try:
            cls, op = self.parse_req(req)
        except:
            self.log_error('Bad request: %s', req)
            self.return_error(400, 'bad request')
            return

        if (cls in DataService.classes_keys):
            with error_handler(self):
                DataService.classes[cls].GET(self, session, params, op)
        else:
            self.log_error('Bad GET: %s', self.path)
            self.return_error(400, 'bad request')

    def do_OPTIONS(self):
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST')
            self.send_header('Access-Control-Max-Age', '86400')
            self.send_header('Content-Type', 'text/html; charset=UTF-8')
            self.send_header('Content-Length', '0')

            self.end_headers()
            self.wfile.flush()
        except:
            Log.error("Error handling OPTIONS")

    def get_bool(self, params, name, defval = None):
        val = self.get_str(params, name, defval)
        try:
            return bool(val)
        except ValueError:
            raise WrongArgs("argument '%s' is not bool" % name)

    def get_int(self, params, name, defval = None):
        val = self.get_str(params, name, defval)
        try:
            return int(val)
        except ValueError:
            raise WrongArgs("argument '%s' is not int" % name)

    def get_str(self, params, name, defval = None):
        if (params.has_key(name)):
            return params[name]
        elif (defval == None):
            raise WrongArgs("lack of argument '%s'" % name)
        else:
            return defval

class MyServer(SocketServer.ThreadingMixIn, HTTPServer):
    def __init__(self, server_address, HandlerClass):
        BaseServer.__init__(self, server_address, HandlerClass)
        self.Init()

#        ctx = SSL.Context(SSL.SSLv23_METHOD)
        fpem = Config.GetString('BBS_DATASVC_CERT', 'server.pem')
#        ctx.use_privatekey_file(fpem)
#        ctx.use_certificate_chain_file(fpem)
#        self.socket = SSL.Connection(ctx, socket.socket(self.address_family, self.socket_type))
        self.base_socket = socket.socket(self.address_family, self.socket_type)
#        self.base_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.socket = ssl.wrap_socket(self.base_socket,
                certfile=fpem, server_side=True)
        self.server_bind()
        self.server_activate()

    def Init(self):
        Config.LoadConfig()
        BCache.Init()
        BoardManager.Init()
        UCache.Init()
        commondata.CommonData.Init()
        self.fast_indexer_state = fast_indexer.State()
        self.fast_indexer = fast_indexer.FastIndexer(self.fast_indexer_state)
        self.fast_indexer.daemon = True
        self.fast_indexer.start()

def main():
    try:
        userinfo = getpwnam('bbs')
        os.setuid(userinfo[2])
    except:
        Log.error("Failed to find user 'bbs'!")
        sys.exit(1)

    threading.stack_size(1024*1024) # default stack size: 8M. may exhaust virtual address space
    port = 8080
    server = MyServer(('', port), DataService)
    print 'Starting at port %d...' % port
    try:
        server.serve_forever()
    except:
        pass

if __name__ == '__main__':
    main()

