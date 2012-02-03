import struct
from Util import Util
import Config
from sysv_ipc import SharedMemory, ExistentialError

UCACHE_HASHSIZE = 330000
UCACHE_HASHKCHAR = 3
UCACHE_HASHBSIZE = 374

HASH0_SIZE = 26
HASH_SIZE_COL = 226
HASH_SIZE_ROW = 36
HASHTABLE_SIZE = 2 * HASH0_SIZE + 2 * HASH_SIZE_COL * HASH_SIZE_ROW

HASHTABLE_HASH0_POS = 0
HASHTABLE_HASH_POS = HASHTABLE_HASH0_POS + HASH0_SIZE * 2

HASHTABLE_POS = 0
HASHUSAGE_POS = HASHTABLE_POS + HASHTABLE_SIZE
HASHHEAD_POS = HASHUSAGE_POS + HASHTABLE_SIZE
HASHNEXT_POS = HASHHEAD_POS + 4 * (UCACHE_HASHSIZE + 1)
UPTIME_POS = HASHNEXT_POS + 4 * Config.MAXUSERS
NUMBER_POS = UPTIME_POS + 4
USER_TITLE_POS = NUMBER_POS + 4
PASSWD_POS = USER_TITLE_POS + 255 * Config.USER_TITLE_LEN

class UserRecord:
    parser = struct.Struct('=%dsbBI16sII%ds2s%ds%ds%ds%dsIIIi8sIiiII' % (Config.IDLEN + 2, Config.NAMELEN, Config.OLDPASSLEN, Config.MAXCLUB/32 * 4, Config.MAXCLUB / 32 * 4, Config.MD5PASSLEN))
    _fields = [['userid', 1], 'flags', 'title', 'firstlogin', 'lasthost', 'numlogins', 'numposts', 'passwd', 'padding', ['username', 1], ['club_read_rights', 2, '=%dI' % (Config.MAXCLUB/32)], ['club_write_rights', 2, '=%dI' % (Config.MAXCLUB/32)], 'md5passwd', 'userlevel', 'lastlogin', 'stay', 'signature', ['userdef', 2, '=2I'], 'notedate', 'noteline', 'notemode', 'exittime', 'usedspace']
    uid = 0

    # struct userec
    size = parser.size

    def __init__(self, uid):
        self.uid = uid - 1 # 0 internal
        self.unpack()

    def unpack(self):
        Util.Unpack(self, self.parser.unpack(UCache.uidshm.read(self.size, 0x15ee44 + self.size * self.uid)))

    def pack(self):
        UCache.uidshm.write(self.parser.pack(Util.Pack(self)), 0x15ee44 + self.size * self.uid)

class UCache:
    uidshm = None
    UIDSHM_SIZE = 0x15ee44 + Config.MAXUSERS * UserRecord.size

    @staticmethod
    def Init():
        if (UCache.uidshm == None):
            try:
                UCache.uidshm = SharedMemory(Config.Config.GetInt("UCACHE_SHMKEY", 3696), size = UCache.UIDSHM_SIZE)
            except ExistentialError:
                print "Init UCache SHM"
                # not implemented!
                raise Exception("Not implemented: Init UCache SHM")

    @staticmethod
    def SearchUser(name):
        # poor implementation
        for i in range(1, Config.MAXUSERS):
            user = UserRecord(i)
            if (user.userid == name):
                return i
        return 0

    @staticmethod
    def GetUser(name):
        for i in range(1, Config.MAXUSERS):
            user = UserRecord(i)
            if (user.userid == name):
                return user

        return None

    @staticmethod
    def GetUserByUid(uid):
        return UserRecord(uid)

    @staticmethod
    def Hash(userid):
        uid_left = userid

        char1 = userid[0]
        uid_left = uid_left[1:]
        if (char1.islower()):
            char1 = char1.upper()
        char1 = ord(char1) - ord('A');
        if (char1 < 0 or char1 > 25):
            return 0

        char1 = UCache.GetHash0(char1)

        while (char1 < 0):
            char1 = - char1 - 1
            if (uid_left == ''):
                char1 = UCache.GetHash(char1, 0)
            else:
                char2 = uid_left[0]
                uid_left = uid_left[1:]
                # 0-9 -> 0-9  a-z -> 10-35  A-Z -> 10-35
                if (char2.isalpha()):
                    char2 = ord(char2.lower()) - ord('a') + 10
                else:
                    char2 = ord(char2) - ord('0')
                if (char2 < 0 or char2 > 35):
                    return 0
                char1 = UCache.GetHash(char1, char2)

        char1 = (char1 * UCACHE_HASHBSIZE) % UCACHE_HASHSIZE + 1;

        if (uid_left == ''):
            return char1;

        char2 = 0
        l = len(uid_left)

        while (uid_left != ''):
            ch = ord(uid_left[0])
            uid_left = uid_left[1:]
            if (ch >= ord('a') and (ch <= ord('z'))):
                ch -= 32
            char2 += (ch - 47) * l
            l = l - 1

        char1 = (char1 - 1 + char2 % UCACHE_HASHBSIZE) % UCACHE_HASHSIZE + 1;
        return char1

    @staticmethod
    def GetHash0(index):
        return UCache.GetShort(HASHTABLE_POS + HASHTABLE_HASH0_POS + 2 * index)

    @staticmethod
    def GetHash(x, y):
        return UCache.GetShort(HASHTABLE_POS + HASHTABLE_HASH_POS + 2 * (HASH_SIZE_ROW * x + y))

    @staticmethod
    def GetShort(index):
        return struct.unpack('=h', UCache.uidshm.read(2, index))[0]

