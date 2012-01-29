import struct
import Config

class UserInfo:
    _fields = ['active', 'uid', 'pid', 'invisible', 'sockactive', 'sockaddr', 'destuid', 'mode', 'pager', 'in_chat', 'chatid', 'from', 'logintime', 'fill', 'freshtime', 'utmpkey', 'mailbox_prop', 'userid', 'realname', 'username', 'friendsnum', ['friends_uid', 2, '=%di' % MAXFRIENDS ], 'currentboard', 'mailcheck']
    _parser = struct.Struct('=iiiiiiiiii16s%dsi36siiI20s20s40si%dsiI' % (IPLEN + 4, MAXFRIENDS * 4))

    @staticmethod
    def size():
        return 1820

