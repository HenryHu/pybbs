#!/usr/bin/env python
from ConfigParser import *
from StringIO import *
from Log import Log

class Config:
    @staticmethod
    def LoadConfig():
        Config.parser = ConfigParser()
        try:
            sconff = open(CONFIG_FILE, "r")
        except:
            Log.warn("cannot open config file")
            return

        sconf = StringIO()
        sconf.write("[sysconf]\n")
        sconf.write(sconff.read())
        sconf.seek(0)
        Config.parser.readfp(sconf)
        sconff.close()
        sconf.close()
        return

    @staticmethod
    def GetBoardsFile():
        return BOARDS_FILE

    @staticmethod
    def GetInt(name, defval):
        if (Config.parser.has_option('sysconf', name)):
            return Config.parser.getint('sysconf', name)
        else:
            return defval

BBS_ROOT = '/home/bbs/'
BOARDS_FILE = BBS_ROOT + '.BOARDS.TEST'
STRLEN = 80
BM_LEN = 60
MAXBOARD = 400
CONFIG_FILE = BBS_ROOT + 'etc/sysconf.ini'
FILENAME_LEN = 20
OWNER_LEN = 30
SESSIONID_LEN = 32
NAMELEN = 40
IDLEN = 12
MD5PASSLEN = 16
OLDPASSLEN = 14
MAXCLUB = 128
MAXUSERS = 20000
MAX_MSG_SIZE = 1024

