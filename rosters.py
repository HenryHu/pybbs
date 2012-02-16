import copy
import signal
from lxml import builder
import time
from threading import Thread
import traceback

from xmpp import xml
from xmpp.features import NoRoute

import roster
import UserManager
import Msg
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

    __xmlns__ = "jabber:client"

    def __init__(self):
        Thread.__init__(self)

        self.E = builder.ElementMaker(namespace = self.__xmlns__)
        self._rosters = {}
        self._resources = None
        self._session_cache = {}
        self.update_sessions()

        signal.signal(signal.SIGUSR2, Rosters.handle_signal_message)
        signal.signal(signal.SIGABRT, Rosters.handle_signal_abort)

        self._running = True
        self.start()

    @staticmethod
    def handle_signal_abort(signum, frame):
        Log.warn("Someone want to kill me! But I'll not die now! Hahahaha!")

    @staticmethod
    def handle_signal_message(signum, frame):
        Log.info("Someone has sent me a message...")

    def run(self):
        while (self._running):
            time.sleep(Config.XMPP_UPDATE_TIME_INTERVAL)
            try:
                self.update_sessions()
            except Exception as e:
                traceback.print_exc()

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
                    show = session_info.get_show(self.get_user(conn.authJID.bare))
                    elem = conn.E.presence(
                        {'from' : '%s/%s' % (jid, session_info.get_res()),
                         'to' : conn.authJID.bare},
                        conn.E.status(session_info.get_status()),
                        conn.E.priority(session_info.get_priority()))
                    if (show != None):
                        elem.append(conn.E.show(show))
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
        for (fulljid, route) in self.routes(to):
            Log.debug("sending to %s" % fulljid)
            route.handle(elem)

    def get_user(self, jid):
        userid = jid.partition('@')[0]
        return UserManager.UserManager.LoadUser(userid)

    def notify_session(self, jid, session, type = None):
        # notify session changed (online/state change)
        for hisjid in self._rosters:
            roster = self._rosters[hisjid]
            if (jid in roster.watching()):
                # you are watching me, so I'll notify you
                Log.debug("notify %s about %s" % (hisjid, session.get_fulljid()))
                elem = None
                if (type == None):
                    show = session.get_show(self.get_user(hisjid))
                    elem = self.E.presence(
                            {'from' : session.get_fulljid(),
                                'to' : hisjid}, 
                            self.E.status(session.get_status()), 
                            self.E.priority(session.get_priority()))
                    if (show != None):
                        elem.append(self.E.show(show))
                else:
                    elem = self.E.presence(
                            {'from' : session.get_fulljid(),
                                'to' : hisjid,
                                'type' : type})

                try:
                    self.transmit(hisjid, elem)
                except NoRoute:
                    Log.error("notify error: NoRoute")
                    pass

    def update_sessions(self):
        Log.debug("updating sessions")
        new_sessions = self.get_bbs_sessions()
        for jid in self._session_cache:
            notify_sessions = []
            offline_sessions = []
            my_old_sessions = self._session_cache[jid]
            if (jid not in new_sessions): # all logins go offline
                my_new_sessions = []
            else:
                my_new_sessions = new_sessions[jid]

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
                Log.debug("changed or new session: %s" % session.to_string())
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
 
    def send_msg(self, from_jid, to_jid, text):
        maysend = False
        from_userid, from_sessionid = self.get_session_info(from_jid)
        to_userid, to_sessionid = self.get_session_info(to_jid)
        if (not to_jid in self._session_cache):
            return -14

        errcode = 0
        to_pid = 0
        for session in self._session_cache[to_jid]:
            ret = Msg.Msg.MaySendMsg(from_userid, to_userid, session._userinfo)
            if (ret > 0):
                maysend = True
                to_pid = session._userinfo.pid
            if (ret < 0):
                errcode = ret

        if (not maysend):
            Log.warn("may not send from %s to %s err %d" % (from_jid, to_jid, errcode))
            return errcode

        ret = Msg.Msg.SaveMsg(from_userid, to_userid, to_pid, text)
        if (ret < 0):
            Log.error("savemsg() fail! from %s to %s err %d" % (from_userid, to_userid, ret))
            return ret

        errcode = 1
        for session in self._session_cache[to_jid]:
            ret = Msg.Msg.NotifyMsg(from_userid, to_userid, session._userinfo)
            if (ret > 0):
                notified = True
            if (ret < 0):
                errcode = ret

        if (notified):
            return 1
        else:
            Log.warn("notifymsg() fail: err %d" % errcode)
            return errcode


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
        if (self._userinfo.AcceptMsg()):
            return "chat"
        else:
            return None

    def get_show(self, user):
        if (user.CanSendTo(self._userinfo)):
            return self.get_show_natural()
        else:
            return "dnd"

    def get_status(self):
        return Util.Util.RemoveTags(Util.Util.gbkDec(self._userinfo.username))

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
                self._userinfo.friendsnum == other._userinfo.friendsnum and
                self._userinfo.friends_uid == other._userinfo.friends_uid)

    def to_string(self):
        return "jid: %s full: %s show: %s status: %s\033[m prio: %s idle: %d" % (
                self.get_jid(), self.get_fulljid(), self.get_show_natural(),
                self.get_status(), self.get_priority(), int(time.time()) - self._userinfo.freshtime)

