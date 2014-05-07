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
import os
from xmpp.features import NoRoute

__disco_info_ns__ = 'http://jabber.org/protocol/disco#info'
__disco_items_ns__ = 'http://jabber.org/protocol/disco#items'
__vcard_ns__ = 'vcard-temp'

STEAL_AFTER_SEEN = 3

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
        if self.rosters.get_xmpp_read(self._user.GetUID()) is None:
            self.rosters.set_xmpp_read(self._user.GetUID(), msgbox.GetMsgCount(all = False) - msgbox.GetUnreadCount())
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

    def get_uid(self):
        return self._user.GetUID()

    def recv_msg(self, from_, msgtext):
        # got a new message! send it!
        elem = self.E.message({'from': from_, 'to': unicode(self.authJID)},
                self.E.body(msgtext))
        self.recv(unicode(self.authJID), elem)

    def check_msg(self):
        Log.debug("checking msg for %s" % self._userid)
        msgbox = MsgBox.MsgBox(self._userid)
        msg_count = msgbox.GetMsgCount(all = False)
        my_pid = os.getpid()
        xmpp_read = self.rosters.get_xmpp_read(self._user.GetUID())
        if xmpp_read > msg_count:
            xmpp_read = 0
        Log.debug("total: %d xmpp read: %d" % (msg_count, xmpp_read))
        self.rosters.set_xmpp_read(self._user.GetUID(), msg_count)
        if xmpp_read < msg_count:
            return xmpp_read
        else:
            return -1

    def deliver_msg(self, start):
        Log.debug("deliver msg to %s" % unicode(self.authJID))
        msgbox = MsgBox.MsgBox(self._userid)
        msg_count = msgbox.GetMsgCount(all = False)
        my_pid = os.getpid()
        for i in range(start, msg_count):
            msghead = msgbox.LoadMsgHead(i, all = False)
            if msghead.topid == my_pid:
                msgtext = msgbox.LoadMsgText(msghead)
                self.recv_msg(self.make_jid(msghead.id), msgtext)

    def steal_msg(self):
        Log.debug("stealing msg for %s" % self._userid)
        msgbox = MsgBox.MsgBox(self._userid)
        msg_count = msgbox.GetMsgCount(all = False)
        msg_unread = msgbox.GetUnreadCount()
        read_count = msg_count - msg_unread
        my_pid = os.getpid()
        term_read = self.rosters.get_term_read(self.get_uid())
        term_stealed = self.rosters.get_term_stealed(self.get_uid())

        all_xmpp = True
        new_unread = {}
        # these are unread msgs!
        for i in range(read_count - 1, msg_count):
            if i < 0: # read_count == 0...
                continue

            msghead = msgbox.LoadMsgHead(i, all = False)
            if i >= read_count and all_xmpp:
                if msghead.topid == my_pid:
                    # still xmpp
                    # RACE!
                    msgbox.GetUnreadMsg()
                else:
                    # not xmpp
                    all_xmpp = False

            if msghead.topid == my_pid:
                # xmpp msg, don't care
                continue

            if i < read_count: # read_count - 1
                session = self.rosters.find_session(self.authJID.bare, msghead.topid)
                if session is None or session.get_mode() != modes.MSG:
                    continue
                Log.debug("considered msg %d as unread" % i)

            # unread msg!
            if msghead.topid not in new_unread:
                Log.debug("for pid %d, first unread at %d" % (msghead.topid, i))
                new_unread[msghead.topid] = i

        final_unread = {}
        to_steal = {}
        to_steal_begin = msg_count

        for pid in term_read:
            if pid in new_unread:
                if new_unread[pid] == term_read[pid][0]:
                    # still unread
                    final_unread[pid] = (term_read[pid][0], term_read[pid][1] + 1)
                    Log.debug(".. still unread: %d for %d, %d times" % (new_unread[pid], pid, term_read[pid][1]+1))
                    if final_unread[pid][1] > STEAL_AFTER_SEEN:
                        to_steal[pid] = final_unread[pid]
                        Log.debug(".. let's steal! %d+ from %d" % (to_steal[pid][0], pid))
                        if pid in term_stealed:
                            steal_begin = max(final_unread[pid][0], term_stealed[pid] + 1)
                        else:
                            steal_begin = final_unread[pid][0]
                        if steal_begin < to_steal_begin:
                            to_steal_begin = steal_begin
                else:
                    # moved forward
                    final_unread[pid] = (new_unread[pid], 1)
                    Log.debug(".. moved: %d->%d for %d" % (term_read[pid][0], new_unread[pid], pid))
            else:
                # disappeared? consider as read
                Log.debug(".. disappeared: %d" % pid)
                pass
        for pid in new_unread:
            if pid not in term_read:
                # new session
                Log.debug(".. new unread: %d for %d" % (new_unread[pid], pid))
                final_unread[pid] = (new_unread[pid], 1)

        if to_steal:
            Log.debug("steal starting from %d" % to_steal_begin)
            for i in range(to_steal_begin, msg_count):
                msghead = msgbox.LoadMsgHead(i, all = False)
                if msghead.topid == my_pid:
                    Log.debug("skip xmpp %d for %d" % (i, msghead.topid))
                    msgbox.GetUnreadMsg()
                elif msghead.topid in to_steal:
                    if msghead.topid not in term_stealed or i > term_stealed[msghead.topid]:
                        Log.debug("steal! %d from %d" % (i, msghead.topid))
                        # not stealed...
                        msgtext = msgbox.LoadMsgText(msghead)
                        self.recv_msg(self.make_jid(msghead.id), msgtext)
                        term_stealed[msghead.topid] = i
                    else:
                        Log.debug("already stealed: %d from %d" % (i, msghead.topid))

        self.rosters.set_term_read(self.get_uid(), final_unread)

    @xmpp.stanza('presence')
    def presence(self, elem):
        """Presence information may be sent out from the client or
        received from another account."""

        #Log.warn("handle presence. me: %r elem: %r" % (self.authJID, elem))
        if self.authJID == elem.get('from'):
            if (elem.get('to') == None or (not self.authJID.match_bare(elem.get('to')))):
                return self.send_presence(elem)
        self.recv_presence(elem)

    def send_presence(self, elem):
        # we want to send a presence
        direct = elem.get('to')
        if not direct:
            # not sending directly to one JID
            # send to everyone who is watching me
            self.rosters.broadcast(self, elem)
            if elem.get('type') != 'probe':
                # if it is not a probe, send a copy to the client also
                self.recv_presence(elem)
            if not self.probed:
                # if we have not probed our watch list, probe them
                self.probed = True
                self.rosters.probe(self)
            # check if rosters will handle this 
        elif not self.rosters.send(self, direct, elem):
            # if not, send it to the JID specified
            self.send(direct, elem)

    def recv_presence(self, elem):
        # we got a precense
        # check if rosters will handle this
        if not self.rosters.recv(self, elem):
            # if not, send this to the client
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


