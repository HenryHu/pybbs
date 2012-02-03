import struct
from Util import Util
import Config
from sysv_ipc import SharedMemory, ExistentialError

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
        raise NotImplementedError
