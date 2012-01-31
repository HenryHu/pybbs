import struct
import Config
from Util import Util

class UserInfo:
    _fields = ['active', 'uid', 'pid', 'invisible', 'sockactive', 'sockaddr', 'destuid', 'mode', 'pager', 'in_chat', 'chatid', 'from', 'logintime', 'fill', 'freshtime', 'utmpkey', 'mailbox_prop', 'userid', 'realname', 'username', 'friendsnum', ['friends_uid', 2, '=%di' % Config.MAXFRIENDS ], 'currentboard', 'mailcheck']
    _parser = struct.Struct('=iiiiiiiiii16s%dsi36siiI20s20s40si%dsiI' % (Config.IPLEN + 4, Config.MAXFRIENDS * 4))

    ACTIVE_POS = 0
    UID_POS = ACTIVE_POS + 4
    PID_POS = UID_POS + 4

    #struct user_info
    size = _parser.size

    def load(self):
        if (self._index < 0):
            raise Exception("Cannot load without index!")
        from Utmp import Utmp
        self.unpack(Utmp.utmpshm.read(UserInfo.size, self._index * UserInfo.size))

    def save(self):
        if (self._index < 0):
            raise Exception("Cannot save without index!")
        from Utmp import Utmp
        Utmp.utmpshm.write(self.pack, UserInfo.size)

    def unpack(self, str):
        Util.Unpack(self, UserInfo._parser.unpack(str))
            
    def pack(self):
        return UserInfo._parser.pack(*Util.Pack(self))

    def __init__(self, idx):
        self._index = idx - 1
        if (idx != 0):
            self.load()

    def GetIndex(self):
        return self._index + 1

    def HasFriend(self, uid):
        if (self.friendsnum <= 0):
            return False, None
        for i in range(self.friendsnum):
            if (self.friends_uid[i] == uid):
                return True, i
        return False, None

