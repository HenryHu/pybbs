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

    @staticmethod
    def GetString(name, defval):
        if (Config.parser.has_option('sysconf', name)):
            val = Config.parser.get('sysconf', name)
            if (val[0] == '"' and val.endswith('"')):
                val = val[1:-1]
            return val.decode('gbk')
        else:
            return defval

BBS_ROOT = '/home/bbs/'
BBS_XMPP_CERT_FILE = BBS_ROOT + "xmpp.crt"
BBS_XMPP_KEY_FILE = BBS_ROOT + "xmpp.key"

BOARDS_FILE = BBS_ROOT + '.BOARDS'
STRLEN = 80
ARTICLE_TITLE_LEN = 60
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
MAXFRIENDS = 400
MAXMESSAGE = 5
MAXSIGLINES = 6
IPLEN = 16
DEFAULTBOARD = "sysop"
BLESS_BOARD = "happy_birthday"
QUOTED_LINES = 10

MAXACTIVE = 8000
USHM_SIZE = MAXACTIVE + 10
UTMP_HASHSIZE = USHM_SIZE * 4
UCACHE_SEMLOCK = 0
LEN_FRIEND_EXP = 15

REFRESH_TIME = 30 # time between friend list update
USER_TITLE_LEN = 18 # used in UCache

XMPP_IDLE_TIME = 300
XMPP_LONG_IDLE_TIME = 1800

XMPP_UPDATE_TIME_INTERVAL = 10

PUBLIC_SHMKEY = 3700
