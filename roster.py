from xmpp import xml
from collections import namedtuple
Item = namedtuple('Item', 'attr groups')

class Roster(object):
    """Roster stores friends information, so we use friend information
    in BBS here."""

    def __init__(self, jid):
        self.jid = jid # my jid ( userid@... )
        self._items = {} # my friends
        self._requests = set() # who requested
        self._last = {} # my last status

    def request(self, conn):
        """Remember that a client requested roster information.  The
        remembered set is used to push roster updates."""

        if conn.authJID not in self._requests:
            jid = conn.authJID
            self._requests.add(jid)
            conn.one(xmpp.StreamClosed, lambda: self.forget(jid))
        return self

    def requests(self):
        """The set of clients that requested this roster."""

        return self._requests

    def presence(self, jid, presense):
        """Update the last presence sent from a client."""

        self._last[jid] = presense
        return self

    def last(self):
        """Iterate over the last presence sent from each client."""

        return self._last.itervalues()

    def forget(self, jid):
        """A client has disconnected."""

        self._requests.discard(jid)
        self._last.pop(jid, None)
        return self

    def items(self):
        """Iterate over all roster items."""

        return (self._to_xml(i) for i in self._items.itervalues())

    def subscribers(self):
        """Iterate over accounts subscribed to this account."""

        return self._match_subscription('both', 'from')

    def watching(self):
        """Iterate over accounts this account is subscribed to."""

        return self._match_subscription('both', 'to')

    def _match_subscription(self, *subs):
        return (
            j for (j, s) in self._items.iteritems()
            if s.attr.get('subscription') in subs
        )

    def set(self, item):
        """Add / remove friend"""

        jid = item.get('jid')
        if item.get('subscription') == 'remove':
            self._items.pop(jid, None)
            return None
        else:
            state = self._items[jid] = self._merge(jid, self._from_xml(item))
            return self._to_xml(state)

    def update(self, jid, **attr):
        """Update roster state."""

        return self._updated(self._get(jid), **attr)

    def ask(self, contact):
        """Update roster state to reflect a new subscription request."""

        return self.subscribe(contact, 'none', ask='subscribe')

    def subscribe(self, jid, new, ask=None):
        """Subscribe to this roster: add friend"""

        state = self._get(jid)
        old = state.attr.get('subscription')
        if old is None:
            pass
        elif new == 'none':
            new = old
        elif ((new == 'to' and old == 'from')
              or (new == 'from' and old == 'to')):
            new = 'both'
        return self._updated(state, ask=ask, subscription=new)

    def _get(self, jid):
        state = self._items.get(jid)
        if state is None:
            state = self._items[jid] = self._create(jid)
        return state

    def _updated(self, state, **attr):
        state.attr.update(attr)
        return self._to_xml(state)

    def _create(self, jid):
        return Item({ 'jid': jid, 'name': '', 'subscription': 'none' }, [])

    def _merge(self, jid, new):
        old = self._items.get(jid)
        if old is not None:
            for key in old.attr:
                if new.attr.get(key) is None:
                    new.attr[key] = old.attr[key]
        return new

    def _from_xml(self, item):
        return Item({
            'jid': item.get('jid'),
            'name': item.get('name'),
            'subscription': item.get('subscription'),
            'ask': item.get('ask')
        }, [g.text for g in item])

    def _to_xml(self, state):
        (attr, groups) = state
        return xml.E.item(
            dict(i for i in attr.iteritems() if i[1] is not None),
            *[xml.E.group(g) for g in groups]
        )


