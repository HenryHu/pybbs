import copy
from xmpp import xml
from lxml import builder
import time
from thraeding import Thread

import roster
import UserManager
import Config
import Utmp
from Log import Log
import Login
import UserInfo
import Util

class Rosters(Thread):
    """Rosters: Friend lists of different users.
    Friends are already stored in UserInfo. We may just use it.
    We may have caches similar to user_record"""

    def __init__(self):
        Thread.__init__(self)
        self._rosters = {}
        self._resources = None
        self._session_cache = {}
        self.update_sessions()
        self._running = True
        self.E = builder.ElementMaker()
        self.start()

    def run(self):
        while (self._running):
            time.sleep(Config.Config.XMPP_UPDATE_TIME_INTERVAL)
            self.update_sessions()

    def set_resources(self, resources):
        if (self._resources == None):
            self._resources = resources

    def get(self, conn):
        """Get a connection's roster and remember the request."""

        return self._get(conn).request(conn)

    def _get(self, conn):
        bare = conn.authJID.bare
        aroster = self._rosters.get(bare)
        if aroster is None:
            ## Automatically create an empty roster.
            aroster = self._rosters[bare] = roster.Roster(bare, conn)
        return aroster

    def broadcast(self, conn, elem):
        """Send presence information to everyone subscribed to this
        account.
        We do not need to consider the people logined through term"""

        roster = self._get(conn)
        for jid in roster.presence(conn.authJID, elem).subscribers():
            conn.send(jid, elem)

    def probe(self, conn):
        """Ask everybody this account is subscribed to for a status
        update.  This is used when a client first connects.
        Also fake responses from TERM users"""

        roster = self._get(conn)
        elem = conn.E.presence({'from': unicode(conn.authJID), 'type': 'probe'})
        for jid in roster.watching():
            conn.send(jid, elem)
            if (jid != conn.authJID.bare): # bug somewhere, if they are equal..
                for session_info in self.get_bbs_online(jid):
                    elem = conn.E.presence(
                        {'from' : '%s/%s' % (jid, session_info.get_res()),
                         'to' : conn.authJID.bare},
                        conn.E.show(session_info.get_show(self.get_user(conn.authJID.bare))),
                        conn.E.status(session_info.get_status()),
                        conn.E.priority(session_info.get_priority()))
                    conn.send(conn.authJID.bare, elem)

    def send(self, conn, to, elem):
        """Send a subscription request or response."""

        method = getattr(self, 'send_%s' % elem.get('type'), None)
        return method and method(conn, xml.jid(to).bare, elem)

    def send_subscribe(self, conn, contact, pres):
        roster = self.get(conn)
        self.confirm(conn, roster, roster.ask(contact))
        pres.set('to', contact)
        pres.set('from', conn.authJID.bare)
        return conn.send(contact, pres)

    def send_subscribed(self, conn, contact, pres):
        roster = self.get(conn)
        self.confirm(conn, roster, roster.subscribe(contact, 'from'))
        pres.set('to', contact)
        pres.set('from', conn.authJID.bare)
        return self._last(roster, contact, conn.send(contact, pres))

    def _last(self, roster, jid, conn):
        """Send the last presence information for this account to a
        newly subscribed JID."""

        for last in roster.last():
            last = copy.deepcopy(last)
            last.set('to', jid)
            conn.send(jid, last)
        return conn

    def recv(self, conn, elem):
        """Handle subscription requests or responses to this account.
        Reply to probes without involving the client."""

        method = getattr(self, 'recv_%s' % elem.get('type'), None)
        return method and method(conn, elem)

    def recv_subscribe(self, conn, pres):
        return conn.write(pres)

    def recv_subscribed(self, conn, pres):
        roster = self.get(conn)
        contact = xmpp.jid(pres.get('from')).bare
        self.confirm(conn, roster, roster.subscribe(contact, 'to'))
        pres.set('from', contact)
        pres.set('to', conn.authJID.bare)
        return conn.write(pres)

    def recv_probe(self, conn, pres):
        return self._last(self._get(conn), pres.get('from'), conn)

    def confirm(self, conn, roster, item):
        conn.push(roster, conn.E.query({ 'xmlns': 'jabber:iq:roster' }, item))

    def routes(self, jid):
        return self._resources.routes(xml.jid(jid))

    def transmit(self, to, elem):
        for (fulljid, route) in self.routes(jid):
            route.handle(elem)

    def get_user(self, jid):
        userid = jid.partition('@')[0]
        return UserManager.UserManager.LoadUser(userid)

    def notify_session(self, jid, session, show = None):
        # notify session changed (online/state change)
        if (self._resources == None):
            return
        if (show == None):
            show = session.get_show(self.get_user(jid))
        for roster in self.rosters:
            if (jid in roster.watching()):
                # you are watching me, so I'll notify you
                elem = self.E.presence(
                    {'from' : session.get_fulljid(),
                     'to' : jid}, 
                    self.E.show(show),
                    self.E.status(session_info.get_status()), 
                    self.E.priority(session_info.get_priority()))

                self.transmit(jid, elem)

    def update_sessions(self):
        Log.debug("updating sessions")
        new_sessions = self.get_bbs_sessions()
        notify_sessions = []
        offline_sessions = []
        for jid in self._session_cache:
            my_old_sessions = self._session_cache[jid]
            if (jid not in new_sessions): # all logins go offline
                my_new_sessions = []
            else:
                my_new_sessions = new_sessions[i]

            for session in my_old_sessions:
                found = False
                for new_session in my_new_sessions:
                    if (session == new_session): # same jid, same loginid
                        found = True
                        new_session.set_found()
                        if (session.all_same(new_session)):
                            # nothing changed...
                            pass
                        else:
                            notify_sessions.append(new_session)
                if (not found):
                    offline_sessions.append(session)
            for new_session in my_new_sessions:
                if (not new_session.found()):
                    # new session!
                    notify_sessions.append(new_session)

            for session in notify_sessions:
                Log.debug("changed session: %s" % session.to_string())
                self.notify_session(jid, session)
            for session in offline_sessions:
                Log.debug("offline session: %s" % session.to_string())
                self.notify_session(jid, session, "unavailable")
        for jid in new_sessions:
            if (jid not in self._session_cache):
                # new user!
                for session in new_sessions[jid]:
                    Log.debug("new session: %s" % session.to_string())
                    self.notify_session(jid, session)

        self._session_cache = new_sessions

    def get_bbs_sessions(self):
        new_sessions = {}
        lockfd = Utmp.Utmp.Lock()
        try:
            login = Login.Login.list_head()
            seen = set()
            if (login != None): # if list is not empty
                while (True):
                    session = SessionInfo(login.get_loginid())
                    if (session.get_jid() in new_sessions):
                        new_sessions[session.get_jid()].append(session)
                    else:
                        new_sessions[session.get_jid()] = [session]
                    seen.add(login.get_loginid())

                    login = login.list_next()
                    if (login == Login.Login.list_head()):
                        break
                    if (login.get_loginid() in seen):
                        Log.warn("get_bbs_sessions(): LOOP in UtmpHead.LIST!")
                        break
        finally:
            Utmp.Utmp.Unlock(lockfd)

        return new_sessions

    def get_bbs_online(self, jid):
        """ Look at the cache, and figure out online sessions """

        if (jid in self._session_cache):
            return self._session_cache[jid]
        else:
            return []

### Rosters

class SessionInfo(object):
    def __init__(self, loginid):
        self._loginid = loginid
        self._userinfo = UserInfo.UserInfo(loginid)
        self._found = False

    def get_jid(self):
        return "%s@%s" % (self._userinfo.userid, Config.Config.GetString("BBS_XMPP_HOST", "localhost"))

    def get_fulljid(self):
        return "%s/%s" % (self.get_jid(), self.get_res())

    def get_show_natural(self):
        inactive_time = int(time.time()) - self._userinfo.freshtime
        if (inactive_time > Config.XMPP_LONG_IDLE_TIME):
            return "xa"
        if (inactive_time > Config.XMPP_IDLE_TIME):
            return "away"
        return "chat"

    def get_show(self, user):
        if (user.CanSendTo(self._userinfo)):
            return self.get_show_natural()
        else:
            return "dnd"

    def get_status(self):
        return Util.Util.gbkDec(self._userinfo.username)

    def get_res(self):
        return "session%d" % self._loginid

    def get_priority(self):
        inactive_time = int(time.time()) - self._userinfo.freshtime
        if (inactive_time > Config.XMPP_LONG_IDLE_TIME):
            return "-2"
        if (inactive_time > Config.XMPP_IDLE_TIME):
            return "-1"
        return "0"

    def set_found(self):
        self._found = True

    def found(self):
        return self._found

    def __eq__(self, other):
        if (other == None):
            return False
        return (self.get_fulljid() == other.get_fulljid())

    def all_same(self, other):
        if (other == None):
            return False
        return (self.get_fulljid() == other.get_fulljid() and
                self.get_show_natural() == other.get_show_natural() and
                self.get_status() == other.get_status() and
                self.get_priority() == other.get_priority() and
                # match CanSendTo()
                self._userinfo.pager == other._userinfo.pager and
                self._userinfo.friendsnum == other._usreinfo.friendsnum and
                self._userinfo.friends_uid == other._userinfo.friends_uid)

    def to_string(self):
        return "jid: %s full: %s show: %s status: %s prio: %s" % (
                self.get_jid(), self.get_fulljid(), self.get_show_natural(),
                self.get_status(), self.get_priority())

