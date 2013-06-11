import struct
import Config
from Util import Util

ALL_PAGER = 0x1
FRIEND_PAGER = 0x2
ALLMSG_PAGER = 0x4
FRIENDMSG_PAGER = 0x8

CHECK_MAIL = 0x1
CHECK_MSG = 0x2

class UserInfo:
    _fields = ['active', 'uid', 'pid', 'invisible', 'sockactive', 'sockaddr', 'destuid', 'mode', 'pager', 'in_chat', ['chatid', 1], ['from', 1], 'logintime', 'fill', 'freshtime', 'utmpkey', 'mailbox_prop', ['userid', 1], ['realname', 1], ['username', 1], 'friendsnum', ['friends_uid', 2, '=%di' % Config.MAXFRIENDS ], 'currentboard', 'mailcheck']
    _parser = struct.Struct('=iiiiiiiiii16s%dsi36siiI20s20s40si%dsiI' % (Config.IPLEN + 4, Config.MAXFRIENDS * 4))

    ACTIVE_POS = 0
    UID_POS = ACTIVE_POS + 4
    PID_POS = UID_POS + 4
    INVISIBLE_POS = PID_POS + 4
    SOCKACTIVE_POS = INVISIBLE_POS + 4
    SOCKADDR_POS = SOCKACTIVE_POS + 4
    DESTUID_POS = SOCKADDR_POS + 4
    MODE_POS = DESTUID_POS + 4
    PAGER_POS = MODE_POS + 4
    INCHAT_POS = MODE_POS + 4
    USERID_POS = 0x80
    USERID_SIZE = 20

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
        Utmp.utmpshm.write(self.pack(), self._index * UserInfo.size)

    def GetInt(self, offset):
        from Utmp import Utmp
        return struct.unpack('=i', Utmp.utmpshm.read(4, self._index * UserInfo.size + offset))[0]

    def GetMode(self):
        return self.GetInt(UserInfo.MODE_POS)

    def unpack(self, str):
        Util.Unpack(self, UserInfo._parser.unpack(str))
            
    def pack(self):
        try:
            result = UserInfo._parser.pack(*Util.Pack(self))
        except Exception as e:
            print Util.Pack(self)
            raise e
        return result

    def __init__(self, idx = 0):
        self._index = idx - 1
        if (idx != 0):
            self.load()
        else:
            Util.InitStruct(self)
        self.friends_nick = []

    def GetIndex(self):
        return self._index + 1

    def SetIndex(self, index):
        self._index = index - 1

    def HasFriend(self, uid):
        if (self.friendsnum <= 0):
            return False, None
        for i in range(self.friendsnum):
            if (self.friends_uid[i] == uid):
                return True, i
        return False, None

    def GetNick(self, i):
        if (len(self.friends_nick) >= i):
            return None
        return self.friends_nick[i]

    def AcceptMsg(self, friend = False):
        if (friend):
            return self.pager & FRIENDMSG_PAGER
        else:
            return self.pager & ALLMSG_PAGER

    def SetMailCheck(self):
        self.mailcheck &= ~CHECK_MAIL
        self.save()

