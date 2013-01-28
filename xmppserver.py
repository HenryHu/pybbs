import time

import UserManager
import UserInfo
from Session import Session
from Log import Log
import UCache
import Config
import MsgBox
import xmpp
import modes
import Util
import traceback
from xmpp.features import NoRoute

__disco_info_ns__ = 'http://jabber.org/protocol/disco#info'
__disco_items_ns__ = 'http://jabber.org/protocol/disco#items'
__vcard_ns__ = 'vcard-temp'

class XMPPServer(xmpp.Plugin):
    """XMPP server for the BBS"""

    def __init__(self, rosters, host):
        self.probed = False
        self._closed = False
        self.rosters = rosters
        self._session = None

        self.rosters.set_resources(self.get_resources())

        self._fixedjid = UCache.UCache.formalize_jid(unicode(self.authJID))
        self._userid = self._fixedjid.partition('@')[0].encode("gbk")

        if (not self.rosters.allow_login(self.authJID.bare)):
            Log.warn("user %s login denied" % self._userid)
#            self.unbind_res()
            self.stream_error('policy-violation', 'Login denied. Too many logins?')
            return
        Log.info("%s: session start" % unicode(self.authJID))

        if self.authJID.resource[:-8] != "Resource" and len(self.authJID.resource) > 8:
            try:
                routes = self.routes(self.authJID.bare)
                for route in routes:
                    jid = route[0]
                    if jid.resource[:-8] == self.authJID.resource[:-8]:
                        if jid.resource != self.authJID.resource:
                            # old resource!
                            Log.info("old jid: %s %r" % (jid.full, route[1]))
                            route[1].stream_error('conflict', 'A new client with the same resource connected')
                    else:
                        Log.info("another me: %s %r" % (jid.full, route[1]))
            except NoRoute:
                pass
            Log.debug("%s: checked for old sessions" % self.authJID.full)

        # Login the user
        self._user = UserManager.UserManager.LoadUser(self._userid)
        if (self._user == None):
            raise Exception("How can that be!")
        self._peer_addr = self.getpeername()
        self._session = Session(self._user, self._peer_addr[0])
        self._session.RecordLogin()
        # insert into global session list!
        self._userinfo = self._session.Register()
        self._loginid = self._session.utmpent
        self._hostname = host
        self.bind(xmpp.ReceivedCloseStream, self.recv_close)
        self.bind(xmpp.StreamClosed, self.stream_closed)
        self.bind(xmpp.SentCloseStream, self.sent_close)

        self.rosters.register_conn(self)

        msgbox = MsgBox.MsgBox(self._userid)
        self._read_msgs = msgbox.GetMsgCount(all = False) - msgbox.GetUnreadCount()
        if (msgbox.GetUnreadCount() > 0):
            self.check_msg()

    def get_loginid(self):
        return self._loginid

    def recv_close(self):
        Log.debug("%s: close because he wants to" % self.authJID.full)
        return self.close()

    def stream_closed(self):
        Log.debug("%s: close because stream closed" % self.authJID.full)
        return self.close()

    def sent_close(self):
        Log.debug("%s: close because we want to" % self.authJID.full)
        return self.close()

    def close(self):
        if (self._closed):
            Log.debug("already closed. ignore")
            return
        self._closed = True
        Log.info("%s: session end" % unicode(self.authJID))
        if (self._session):
            self._session.Unregister()
        self.unbind_res()
        self.rosters.unregister_conn(self)

    @xmpp.iq('{urn:xmpp:ping}ping')
    def ping(self, iq):
        """Handle ping requests"""

        self.refresh()
        return self.iq('result', iq)

    @xmpp.stanza('message')
    def message(self, elem):
        """Proxy message from one user to another"""

        # so, possible:
        # XMPP user -> Old user
        # XMPP user -> XMPP user => make it like XMPP->old

        # Old user -> XMPP user (emulated) => handled elsewhere

        to_jid = elem.get('to')
        from_jid = elem.get('from')
        if (from_jid == None):
            return

#       self.recv(to_jid, elem)

        text_body = None
        for child in elem:
            if (child.tag.endswith('}body')):
                text_body = child.text
        if (text_body == None):
            return

        ret = self.rosters.send_msg(from_jid, to_jid, text_body)
        if (ret <= 0):
            Log.warn("sendmsg() failed to %s from %s error %d" % (to_jid, from_jid, ret))
            errors = { 
                    -1 : "That user has locked screen, please send later.",
                    -11: "That user denied your message.",
                    -12: "That user has too many unread messages. Please send later.",
                    -13: "User has gone after message sent.",
                    -14: "User has gone before message sent.",
                    -2 : "User has gone before message sent.",
                    -21: "Error when sending message!"}
            if (ret in errors):
                elem = self.E.message({'from': to_jid,
                    'to': from_jid,
                    'type': 'error'},
                    self.E.body(errors[ret]))
                self.recv(from_jid, elem)
            # -2: no perm to see cloak
            # 0: error
            # -1: lockscreen
            # -11: blocked
            # -12: too many messages
            # -13: user gone when notifying
            # -14: user gone before saving
            # -21: error when saving message

    def make_jid(self, userid):
        return "%s@%s" % (userid, self._hostname)

    def refresh(self):
        self._userinfo.freshtime = int(time.time())
        self._userinfo.save()

    def ping_result(self, iq):
        self.refresh()

    def ping_client(self):
        try:
            pingelem = self.E.ping(xmlns='urn:xmpp:ping')
            return self.iq('get', self.ping_result, pingelem)
        except Exception as e:
            Log.debug("ping client %r failed: %r" % (self.authJID, e))
            Log.debug(traceback.format_exc())
            return False

    def check_msg(self):
        Log.debug("checking msg for %s" % self._userid)
        msgbox = MsgBox.MsgBox(self._userid)
        msg_count = msgbox.GetMsgCount(all = False)
        if (msg_count > self._read_msgs):
#            Log.debug("total: %d read: %d" % (msg_count, self._read_msgs))
            for i in range(self._read_msgs, msg_count):
                msghead = msgbox.LoadMsgHead(i, all = False)
                if (time.time() - msghead.time < 5):
                    msgtext = msgbox.LoadMsgText(msghead)
#                Log.debug("from: %s text: %s" % (msghead.id, msgtext))

                    # got a new message! send it!
                    elem = self.E.message({'from': self.make_jid(msghead.id), 
                                           'to': unicode(self.authJID)},
                                          self.E.body(msgtext))
                    self.recv(unicode(self.authJID), elem)
            # clear unread...
            for i in range(msg_count):
                if (msgbox.GetUnreadMsg() < 0):
                    break
            self._read_msgs = msg_count
        else:
            if (msg_count < self._read_msgs):
                # <? someone cleared it...
                self._read_msgs = 0

    @xmpp.stanza('presence')
    def presence(self, elem):
        """Presence information may be sent out from the client or
        received from another account."""

        if self.authJID == elem.get('from'):
            if (elem.get('to') == None or (not self.authJID.match_bare(elem.get('to')))):
                return self.send_presence(elem)
        self.recv_presence(elem)

    def send_presence(self, elem):
        direct = elem.get('to')
        if not direct:
            self.rosters.broadcast(self, elem)
            if elem.get('type') != 'probe':
                self.recv_presence(elem)
            if not self.probed:
                self.probed = True
                self.rosters.probe(self)
        elif not self.rosters.send(self, direct, elem):
            self.send(direct, elem)

    def recv_presence(self, elem):
        if not self.rosters.recv(self, elem):
            self.write(elem)

    @xmpp.iq('{jabber:iq:roster}query')
    def roster(self, iq):
        """A roster is this account's list of contacts; it may be
        fetched or updated."""

        roster = self.rosters.get(self)
        method = getattr(self, '%s_roster' % iq.get('type'))
        return method and method(iq, roster)

    def get_roster(self, iq, roster):
        query = self.E.query({ 'xmlns': 'jabber:iq:roster' })
        for item in roster.items():
            query.append(item)
        return self.iq('result', iq, query)

    def set_roster(self, iq, roster):
        query = self.E.query(xmlns='jabber:iq:roster')
        for item in iq[0]:
            result = roster.set(item)
            if result is not None:
                query.append(result)
        if len(query) > 0:
            self.push(roster, query)
        return self.iq('result', iq)

    def push(self, roster, query):
        """Push roster changes to all clients that have requested this
        roster."""

        for jid in roster.requests():
            for (to, route) in self.routes(jid):
                route.iq('set', self.ignore, query)

    def ignore(self, iq):
        """An IQ no-op."""

    @xmpp.iq('{vcard-temp}vCard')
    def vcard(self, iq):
        """vCard support: the client requests its vCard after
        establishing a session."""

        if iq.get('type') == 'get':
            if (iq.get('to') == None):
                target = iq.get('from')
            else:
                target = iq.get('to')

            form_target = UCache.UCache.formalize_jid(target)
            name = form_target.partition('@')[0]
            user = UserManager.UserManager.LoadUser(name)
            info = user.GetInfo()
            desc = '''\r
Logins: %d\r
Posts: %d\r
Last login: %s from %s\r
Experience: %d\r
Performance: %d\r
Life: %d\r
''' % (info['numlogins'], info['numposts'], info['lastlogintime'], 
        info['lasthost'], info['exp'], info['perf'], info['life'])
            if ('plan' in info):
                desc += "Plan:\r%s" % (info['plan'].replace('\n', '\r\n'))

            vcard = self.E.vCard({'xmlns': 'vcard-temp'},
                self.E('FN', name),
                self.E('NICKNAME', Util.Util.RemoveTags(info['nick'])),
                self.E('DESC', Util.Util.RemoveTags(desc)))

            if (iq.get('to') == None):
                return self.iq('result', iq, vcard)
            else:
                return self.iq('result', iq, vcard, {'from': iq.get('to')})

    @xmpp.iq('{%s}query' % __disco_info_ns__)
    def disco_info(self, iq):
        """ Service Discovery: disco#info """

        target = iq.get('to')

        if (target.find('@') < 0):
            # query server info
            query = self.E.query({ 'xmlns': __disco_info_ns__},
                self.E.identity({ 'category': 'server',
                                 'type': 'im',
                                 'name': Config.Config.GetString('XMPP_SERVER_IDENTITY_NAME', 'BBS'),
                                }))
            features = [__disco_info_ns__, __disco_items_ns__, __vcard_ns__]
            for feature in features:
                query.append(self.E.feature({'var' : feature}))

        else:
            # query client info
            query = self.E.query({ 'xmlns': __disco_info_ns__},
                self.E.identity({ 'category': 'client',
                                 'type': 'term',
                                 'name': Config.Config.GetString('XMPP_SERVER_IDENTITY_NAME', 'BBS'),
                                }))

            features = [__disco_info_ns__, __disco_items_ns__, __vcard_ns__]
            for feature in features:
                query.append(self.E.feature({'var' : feature}))

        return self.iq('result', iq, query, {'from': target})


    @xmpp.iq('{%s}query' % __disco_items_ns__)
    def disco_items(self, iq):
        """ Service Discovery: disco#items """

        target = iq.get('to')

        if (target.find('@') < 0):
            # query server info
            query = self.E.query({ 'xmlns': __disco_items_ns__})

        else:
            # query client info
            query = self.E.query({ 'xmlns': __disco_items_ns__})

        return self.iq('result', iq, query, {'from': target})


