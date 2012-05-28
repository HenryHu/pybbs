from UCache import UCache
import json
from errors import *

class UserManager:
    users = {}
    @staticmethod
    def HandleLogin(svc, username, passwd):
        user = UserManager.LoadUser(username)
        if (user == None):
            raise Unauthorized('Login failed')

        if (user.Authorize(passwd)):
            session = Session(user, svc.client_address[0])
            ret = {}
            ret['session'] = session.GetID()

            svc.writedata(json.dumps(ret))

        else:
            raise Unauthorized('Login failed')

    @staticmethod
    def LoadUser(user):
        userec = UCache.GetUser(user)
        if (userec == None):
            return None
        user = userec.userid
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
