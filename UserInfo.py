import struct
import Config

class UserInfo:
    _fields = ['active', 'uid', 'pid', 'invisible', 'sockactive', 'sockaddr', 'destuid', 'mode', 'pager', 'in_chat', 'chatid', 'from', 'logintime', 'fill', 'freshtime', 'utmpkey', 'mailbox_prop', 'userid', 'realname', 'username', 'friendsnum', ['friends_uid', 2, '=%di' % Config.MAXFRIENDS ], 'currentboard', 'mailcheck']
    _parser = struct.Struct('=iiiiiiiiii16s%dsi36siiI20s20s40si%dsiI' % (Config.IPLEN + 4, Config.MAXFRIENDS * 4))

    ACTIVE_POS = 0
    UID_POS = ACTIVE_POS + 4
    PID_POS = UID_POS + 4

    @staticmethod
    def size():
        return UserInfo._parser.size

    def unpack(self, str = None):
        if (str):
            Util.Unpack(self, UserInfo._parser.unpack(str))
        else:
            if (self._index < 0):
                raise Exception("Cannot unpack without index!")
            else:
                Util.Unpack(self, UserInfo._parser.unpack(Utmp.utmpshm.read(UserInfo._parser.size, self._index * UserInfo._parser.size)))

    def pack(self):
        return UserInfo._parser.pack(*Util.Pack(self))

    def __init__(self, idx):
        self._index = idx - 1
        if (idx != 0):
            self.unpack()
