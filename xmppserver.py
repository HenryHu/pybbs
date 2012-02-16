from UserManager import UserManager
import UserInfo
from Session import Session
import xmpp
import modes

class XMPPServer(xmpp.Plugin):
    """XMPP server for the BBS"""

    def __init__(self, rosters, host):
        self.probed = False
        self.rosters = rosters

        self.rosters.set_resources(self.get_resources())

        self._userid = self.authJID.bare.partition('@')[0].encode("gbk")
        # Login the user
        self._user = UserManager.LoadUser(self._userid)
        if (self._user == None):
            raise Exception("How can that be!")
        self._peer_addr = self.getpeername()
        self._session = Session(self._user, self._peer_addr[0])
        # insert into global session list!
        self._userinfo = self._session.Register()
        self._hostname = host
        self.bind(xmpp.ReceivedCloseStream, self.close)

    def close(self):
        if (self._session):
            self._session.Unregister()
        self.unbind_res()

    @xmpp.iq('{urn:xmpp:ping}ping')
    def ping(self, iq):
        """Handle ping requests"""

        return self.iq('result', iq)

    def get_session_info(self, jid):
        userid = jid.partition('@')[0]
        resource = ''
        sessionid = None
        try:
            resource = jid.partition('/')[1]

            if (resource.find('session') == 0):
                sessionid = int(resource[7:])
        except Exception:
            pass

        return userid, sessionid

    @xmpp.stanza('message')
    def message(self, elem):
        """Proxy message from one user to another"""

        # so, possible:
        # XMPP user -> Old user
        # XMPP user -> XMPP user => make it like XMPP->old

        # Old user -> XMPP user (emulated) => handled elsewhere

        to_jid = elem.get('to')
        to_userid, to_sessionid = self.get_session_info(to_jid)
        if (to_sessionid == None):
            self.recv(to_jid, elem)
            return

        to_userinfo = UserInfo.UserInfo(to_sessionid)
        if (to_userinfo.mode == modes.XMPP):
            self.recv(to_jid, elem)
            return

        text_body = None
        for child in elem:
            if (child.tag.endswith('}body')):
                text_body = child.text
        if (text_body == None):
            return

        from_jid = elem.get('from')
        if (from_jid == None):
            return
        from_userid, from_sessionid = self.get_session_info(from_jid)

        ret = Msg.SendMsg(from_userid, to_userid, to_userinfo, text_body)
        if (ret <= 0):
            Log.warn("sendmsg() failed to %s from %s error %d" % (to_userid, from_userid, ret))
            # -2: no perm to see cloak
            # 0: error
            # -1: lockscreen
            # -11: blocked
            # -12: too many messages
            # -13: user gone when notifying
            # -14: user gone before saving
            # -21: error when saving message

    @xmpp.stanza('presence')
    def presence(self, elem):
        """Presence information may be sent out from the client or
        received from another account."""

        if self.authJID.match_bare(elem.get('from')):
            return self.send_presence(elem)
        self.recv_presence(elem)

    def send_presence(self, elem):
        direct = elem.get('to')
        if not direct:
            self.rosters.broadcast(self, elem)
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

    def use_tls(self):
        return True

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
        """Fake vCard support: the client requests its vCard after
        establishing a session; send an empty one."""

        if iq.get('type') == 'get':
            return self.iq('result', iq, self.E.vCard(
                { 'xmlns': 'vcard-temp' },
                self.E('FN', 'No Name')
            ))


