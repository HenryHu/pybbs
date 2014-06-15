import struct
from Util import Util
from Log import Log
import Config
from sysv_ipc import SharedMemory, ExistentialError
from cstruct import *

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
PASSWD_POS = USER_TITLE_POS + 255 * Config.USER_TITLE_LEN + 2 # align

USEREC_USERID_POS = 0

@init_fields
class UserRecord(object):
    _fields = [
        ['userid' , Str(Config.IDLEN + 2)],
        ['flags' , I8()],
        ['title' , U8()],
        ['firstlogin' , U32()],
        ['lasthost' , Str(16)],
        ['numlogins' , U32()],
        ['numposts' , U32()],
        ['passwd' , FixStr(Config.OLDPASSLEN)],
        ['padding' , FixStr(2)],
        ['username' , Str(Config.NAMELEN)],
        ['club_read_rights' , Array(I32, Config.MAXCLUB / 32)],
        ['club_write_rights' , Array(I32, Config.MAXCLUB / 32)],
        ['md5passwd' , FixStr(Config.MD5PASSLEN)],
        ['userlevel' , U32()],
        ['lastlogin' , U32()],
        ['stay' , U32()],
        ['signature' , I32()],
        ['userdef' , Array(I32, 2)],
        ['notedate' , U32()],
        ['noteline' , I32()],
        ['notemode' , I32()],
        ['exittime' , U32()],
        ['usedspace' , U32()]
    ]
    def __init__(self, uid):
        self.uid = uid - 1 # 0 internal
        if uid == 0:
            self.buf = '\0' * self.size

    def read(self, pos, len):
        if self.uid == -1:
            return self.buf[pos:pos+len]
        else:
            return UCache.uidshm.read(len, PASSWD_POS + self.size * self.uid + pos)

    def write(self, pos, data):
        assert pos >= 0
        assert pos < self.size
        assert pos + len(data) <= self.size
        if self.uid == -1:
            self.buf = self.buf[:pos] + data + self.buf[pos+len(data):]
        else:
            UCache.uidshm.write(data, PASSWD_POS + self.size * self.uid + pos)

    def GetUID(self):
        return self.uid + 1

    def Allocate(self, uid):
        self.uid = uid - 1
        self.write(0, self.buf)

class UCache:
    uidshm = None
    UIDSHM_SIZE = PASSWD_POS + Config.MAXUSERS * UserRecord.size

    @staticmethod
    def Init():
        if (UCache.uidshm == None):
            try:
                Log.info("Attaching to UCACHE shared memory")
                UCache.uidshm = SharedMemory(Config.Config.GetInt("UCACHE_SHMKEY", 3696), size = UCache.UIDSHM_SIZE)
            except ExistentialError:
                Log.info("Creating UCACHE shared memory")
                # not implemented!
                raise Exception("Not implemented: Init UCache SHM")
            Log.info("UCache initialization finished")

    @staticmethod
    def SearchUser(name):
        i = UCache.GetHashHead(UCache.Hash(name))
        while (i):
            if (name.lower() == UserRecord(i).userid.lower()):
                return i
            i = UCache.GetNext(i-1)
        return 0
        # poor implementation
#        for i in range(1, Config.MAXUSERS):
#            user = UserRecord(i)
#            if (user.userid == name):
#                return i
#        return 0

    @staticmethod
    def GetUser(name):
        uid = UCache.SearchUser(name)
        if (uid == 0):
            return None

        return UserRecord(uid)

#        for i in range(1, Config.MAXUSERS):
#            user = UserRecord(i)
#            if (user.userid == name):
#                return user

#        return None

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

    @staticmethod
    def GetHashHead(index):
        return UCache.GetInt(HASHHEAD_POS, index)

    @staticmethod
    def GetNext(index):
        return UCache.GetInt(HASHNEXT_POS, index)

    @staticmethod
    def GetInt(base, index):
        return struct.unpack('=i', UCache.uidshm.read(4, base + index * 4))[0]

    @staticmethod
    def DoAfterLogout(user, userinfo, uent, mode):
        pass

    @staticmethod
    def formalize_jid(jid):
        if (jid.find('@') < 0):
            return jid
        userid = jid.partition('@')[0]
        left = jid.partition('@')[2]

        userec = UCache.GetUser(userid)
        if (userec == None):
            return jid
        return "%s@%s" % (userec.userid, left)

    @staticmethod
    def CreateUserRecord(username):
        userec = UserRecord(0)
        userec.userid = username
        return userec
