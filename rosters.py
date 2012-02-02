import copy
from xmpp import xml

class Rosters(object):
    """In a real implementation, roster information would be
    persisted.  This class tracks a roster for each bare JID connected
    to the server."""

    def __init__(self):
        self._rosters = {}

    def get(self, conn):
        """Get a connection's roster and remember the request."""

        return self._get(conn).request(conn)

    def _get(self, conn):
        bare = conn.authJID.bare
        roster = self._rosters.get(bare)
        if roster is None:
            ## Automatically create an empty roster.
            roster = self._rosters[bare] = Roster(bare)
        return roster

    def broadcast(self, conn, elem):
        """Send presence information to everyone subscribed to this
        account."""

        roster = self._get(conn)
        for jid in roster.presence(conn.authJID, elem).subscribers():
            conn.send(jid, elem)

    def probe(self, conn):
        """Ask everybody this account is subscribed to for a status
        update.  This is used when a client first connects."""

        roster = self._get(conn)
        elem = conn.E.presence({'from': unicode(conn.authJID), 'type': 'probe'})
        for jid in roster.watching():
            conn.send(jid, elem)

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


### Rosters


