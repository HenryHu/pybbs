"""bbsauth -- verifies session token

<http://www.ietf.org/rfc/rfc4616.txt>

Copyright (c) 2009, Coptix, Inc.  All rights reserved.
See the LICENSE file for license terms and warranty disclaimer.
"""
from __future__ import absolute_import
from sasl import mechanism as mech, auth

__all__ = ('BBSAuth')

class BBSAuth(mech.Mechanism):
    """The bbsauth mechanism simply submits the optional authorization
    id, the authentication id, and token separated by null
    bytes."""

    NULL = u'\x00'

    def __init__(self, auth):
        self.auth = auth

    def verify(self, *args):
        return self.auth.verify_token(*args)

    state = mech.AuthState

    ## Server

    def challenge(self):
        return self.state(self.verify_challenge, None, '')

    def verify_challenge(self, entity, response):
        try:
            token = response.decode('utf-8')
        except ValueError as exc:
            return self.state(False, entity, None)

        try:
            result = self.verify(token)
            if result:
                entity = entity or self.auth.username()
            return self.state(result, entity, None)
        except auth.PasswordError as exc:
            return self.state(False, entity, None)

    ## Client

    def respond(self, data):
        assert data == ''

        auth = self.auth
        zid = auth.authorization_id()
        cid = auth.username()

        response = self.NULL.join((
            u'' if (not zid or zid == cid) else zid,
            (cid or u''),
            (auth.token() or u'')
        )).encode('utf-8')

        self.authorized = zid or cid
        return self.state(None, zid or cid, response)

