#!/usr/bin/env python
# XMPP service for BBS

"""xmppsvc -- XMPP server

Implements the XMPP server based on BBS user and messaging features
"""

import Config
import xmppserver
import rosters
import xmpp
import xmppauth
import UCache
import Utmp
import commondata
from Log import Log
from pwd import getpwnam
import os
import sys

if __name__ == '__main__':
    try:
        userinfo = getpwnam('bbs')
        os.setuid(userinfo[2])
    except:
        Log.error("Failed to find user 'bbs'!")
        sys.exit(1)

    Config.Config.LoadConfig();
    UCache.UCache.Init()
    Utmp.Utmp.Init()
    commondata.CommonData.Init()

    hostname = Config.Config.GetString("BBS_XMPP_HOST", 'localhost')

    server = xmpp.Server({
        'plugins': [(xmppserver.XMPPServer, { 'rosters': rosters.Rosters() , 'host': hostname})],
        'auth': xmppauth.XMPPAuth('xmpp', hostname, 'bbs'),
        'certfile': Config.BBS_XMPP_CERT_FILE,
        'keyfile': Config.BBS_XMPP_KEY_FILE,
    })

    SP = xmpp.TCPServer(server).bind('0.0.0.0', 5222)
    xmpp.start([SP])
