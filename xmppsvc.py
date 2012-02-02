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

if __name__ == '__main__':

    Config.Config.LoadConfig();
    UCache.UCache.Init()
    Utmp.Utmp.Init()

    hostname = Config.Config.GetString("BBS_XMPP_HOST", 'localhost')

    server = xmpp.Server({
        'plugins': [(xmppserver.XMPPServer, { 'rosters': rosters.Rosters() })],
        'auth': xmppauth.XMPPAuth('xmpp', hostname, 'bbs'),
        'certfile': Config.BBS_XMPP_CERT_FILE,
        'keyfile': Config.BBS_XMPP_KEY_FILE,
    })

    SP = xmpp.TCPServer(server).bind('0.0.0.0', 5222)
    xmpp.start([SP])
