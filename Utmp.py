import Config
from UserInfo import UserInfo
from sysv_ipc import *
from UtmpHead import UtmpHead
# from SemLock import SemLock

UTMPFILE_SIZE = UserInfo.size() * Config.USHM_SIZE
UTMPHEAD_SIZE = 4 * Config.USHM_SIZE + 4 * (Config.UTMP_HASHSIZE + 1) + 4 * 3 + 8 * Config.USHM_SIZE

class Utmp:
    utmpshm = None

    @staticmethod
    def Init():
        if (Utmp.utmpshm == None):
            try:
                Utmp.utmpshm = SharedMemory(Config.Config.GetInt("UTMP_SHMKEY", 3699), size = UTMPFILE_SIZE)
                UtmpHead.utmphead = SharedMemory(Config.Config.GetInt("UTMPHEAD_SHMKEY", 3698), size = UTMPHEAD_SIZE);
            except ExistentialError:
                Utmp.utmpshm = SharedMemory(Config.Config.GetInt("UTMP_SHMKEY", 3699), size = UTMPFILE_SIZE, flags = IPC_CREAT, mode = 0660, init_character='\0')
                UtmpHead.utmphead = SharedMemory(Config.Config.GetInt("UTMPHEAD_SHMKEY", 3698), UTMPHEAD_SIZE, flags = IPC_CREAT, mode = 0660, init_character='\0')
                fd = Utmp.Lock()
                UtmpHead.SetNumber(0);
                UtmpHead.SetHashHead(0, 1);
                for i in range(Config.USHM_SIZE - 1):
                    UtmpHead.SetNext(i, i+2);
                UtmpHead.SetNext(Config.USHM_SIZE - 1, 0);
                Utmp.Unlock(fd);

    @staticmethod
    def Hash(userid):
        hash = UCache.Hash(userid)
        if (hash == 0):
            return 0
        hash = (hash / 3) % Config.UTMP_HASHSIZE;
        if (hash == 0):
            return 1;
        return hash

    @staticmethod
    def Lock():
        #try:
            #SemLock.Lock(Config.UCACHE_SEMLOCK, timeout = 10);
            #return 0;
        #except BusyError:
            #return -1;
        lockf = os.open("UTMP", os.O_RDWR | OS.O_CREAT, 0600)
        if (lockf < 0):
            Log.error("Fail to lock file!")
            raise Exception("fail to lock!")
        Util.FLock(lockf, shared = False)
        return lockf

    @staticmethod
    def Unlock(lockf):
        #SemLock.Unlock(Config.UCACHE_SEMLOCK)
        Util.FUnlock(lockf)

    @staticmethod
    def GetNewUtmpEntry(userinfo):
        utmpfd = Utmp.Lock()
        UtmpHead.SetReadOnly(0)

        userinfo.utmpkey = random.randint(0, 99999999);
        pos = UtmpHead.GetHashHead(0) - 1;
        if (pos == -1):
            UtmpHead.SetReadOnly(1)
            Utmp.Unlock(utmpfd)
            return -1;

        if (UtmpHead.GetListHead() == 0):
            UtmpHead.SetListPrev(pos, pos+1)
            UtmpHead.SetListNext(pos, pos+1)
            UtmpHead.SetListHead(pos+1)
        else:
            i = UtmpHead.GetListHead()
            if (Utmp.GetUserId(i-1).lower() >= userinfo.userid.lower()):
                UtmpHead.SetListPrev(pos, UtmpHead.GetListPrev(i-1))
                UtmpHead.SetListNext(pos, i)
                UtmpHead.SetListPrev(i-1, pos+1)
                UtmpHead.SetListNext(UtmpHead.GetListPrev(pos) - 1, pos+1)
                UtmpHead.SetListHead(pos+1)
            else:
                count = 0;
                i = UtmpHead.GetListNext(i-1)
                while ((Utmp.GetUserId(i-1).lower() < userinfo.userid.lower()) and (i != UtmpHead.GetListHead())):
                    i = UtmpHead.GetListNext(i-1)
                    count = count + 1;
                    if (count > Config.USHM_SIZE):
                        UtmpHead.SetListHead(0)
                        Utmp.RebuildList()
                        UtmpHead.SetReadOnly(1)
                        Utmp.Unlock(utmpfd)
                        return -1 # wrong! exit(-1)!
                UtmpHead.SetListPrev(pos, UtmpHead.GetListPrev(i-1))
                UtmpHead.SetListNext(pos, i)
                UtmpHead.SetListPrev(i-1, pos+1)
                UtmpHead.SetListNext(UtmpHead.GetListPrev(pos) - 1, pos+1)
        UtmpHead.SetHashHead(0, UtmpHead.GetNext(pos))

        if (Utmp.IsActive(pos)):
            if (Utmp.GetPid(pos) != 0):
                Log.warn("allocating an active utmp!")
                os.kill(Utmp.GetPid(pos), os.SIGHUP)
        Utmp.SetUserInfo(pos, userinfo)
        hashkey = Utmp.Hash(userinfo.userid)

        i = UtmpHead.GetHashHead(hashkey);
        UtmpHead.SetNext(pos, i)
        UtmpHead.SetHashHead(hashkey, pos+1)

        UtmpHead.SetNumber(UtmpHead.GetNumber() + 1)
        CommonData.UpdateMaxUser();

        now = int(time.time())
        if ((now > UtmpHead.GetUptime() + 120) or (now < UtmpHead.GetUptime() - 120)):
            UtmpHead.SetUptime(now)
            for n in range(Config.USHM_SIZE):
                if (Utmp.IsActive(n) and Utmp.GetPid(n) != 0 and os.kill(Utmp.GetPid(n), 0) != -1):
                    username = Utmp.GetUserId(n)
                    Utmp.Clear(n+1)
                    User.RemoveMsgCount(username)
        UtmpHead.SetReadOnly(1)
        Utmp.Unlock(utmpfd)
        return pos + 1;

