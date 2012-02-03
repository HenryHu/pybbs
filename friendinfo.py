class FriendInfo:
    def __init__(self, username = '', uid = -1, nick = ''):
        self._username = username
        self._uid = uid
        self._nick = nick

    def get_username(self):
        return self._username

    def get_uid(self):
        return self._uid

    def get_nick(self):
        return self._nick



