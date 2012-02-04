from UserManager import UserManager
import sasl

class XMPPAuth(sasl.auth.Authenticator):
    """To authenticate XMPP users.
    Plan to support 2 methods:
        PLAIN: just username & password
        X-BBS-OAUTH: use OAuth token
    """

    def __init__(self, service_type, host, service_name):
        self._service_type = service_type
        self._host = host
        self._service_name = service_name

    def service_type(self):
        return self._service_type

    def host(self):
        return self._host

    def service_name(self):
        return self._service_name
    
    def username(self):
        raise NotImplementedError

    def password(self):
        raise NotImplementedError

    def get_password(self):
        raise NotImplementedError

    def verify_password(self, authorize, user, passwd):
        """Verity password"""

        if (authorize and user != authorize):
            return False

        user = user.encode("gbk")
#        print "trying to auth %s pass %s" % (user, passwd)
        user = UserManager.LoadUser(user)
        if (user == None):
            return False

        if (user.Authorize(passwd)):
#            print "OK"
            return True

#        print "Wrong PW"
        return False

