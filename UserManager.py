from UCache import UCache
import json

class UserManager:
    users = {}
    @staticmethod
    def HandleLogin(svc, username, passwd):
        user = UserManager.LoadUser(username)
        if (user == None):
            svc.send_response(401, 'Login failed')
            svc.end_headers()
            return

        if (user.Authorize(passwd)):
            session = Session(user, svc.client_address[0])
            ret = {}
            ret['session'] = session.GetID()

            svc.send_response(200, 'OK')
            svc.end_headers()

            svc.wfile.write(json.dumps(ret))

        else:
            svc.send_response(401, 'Login failed')
            svc.end_headers()
            return

    @staticmethod
    def LoadUser(user):
        if (user not in UserManager.users):
            ruser = UserManager.LoadNewUser(user)
            if (ruser == None):
                return None
            UserManager.users[user] = ruser
        return UserManager.users[user]

    @staticmethod
    def LoadNewUser(user):
        userec = UCache.GetUser(user)
        if (userec == None):
            return None

        ruser = User(user, userec)
        return ruser

from Session import Session
from User import User
