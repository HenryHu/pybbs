import Config
import os
import struct
import random
import time
import signal
from User import User
from UCache import UCache
from sysv_ipc import *
from UtmpHead import UtmpHead
from commondata import CommonData
from UserInfo import UserInfo
from Log import Log
from Util import Util
# from SemLock import SemLock

UTMPFILE_SIZE = UserInfo.size * Config.USHM_SIZE
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
        Log.debug("Utmp.Lock enter()")
        lockf = os.open(Config.BBS_ROOT + "UTMP", os.O_RDWR | os.O_CREAT, 0600)
        if (lockf < 0):
            Log.error("Fail to open lock file!")
            raise Exception("fail to lock!")
        Util.FLock(lockf, shared = False)
        Log.debug("Utmp.Lock succ()")
        return lockf

    @staticmethod
    def Unlock(lockf):
        #SemLock.Unlock(Config.UCACHE_SEMLOCK)
        Log.debug("Utmp.Unlock")
        Util.FUnlock(lockf)

    @staticmethod
    def GetNewUtmpEntry(userinfo):
        utmpfd = Utmp.Lock()
        UtmpHead.SetReadOnly(0)

        userinfo.utmpkey = random.randint(0, 99999999);
        pos = UtmpHead.GetHashHead(0) - 1;
        Log.debug("New entry: %d" % pos)
        if (pos == -1):
            UtmpHead.SetReadOnly(1)
            Utmp.Unlock(utmpfd)
            Log.error("Utmp full!")
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
                        Log.error("Utmp list loop!")
                        return -1 # wrong! exit(-1)!
                UtmpHead.SetListPrev(pos, UtmpHead.GetListPrev(i-1))
                UtmpHead.SetListNext(pos, i)
                UtmpHead.SetListPrev(i-1, pos+1)
                UtmpHead.SetListNext(UtmpHead.GetListPrev(pos) - 1, pos+1)
        UtmpHead.SetHashHead(0, UtmpHead.GetNext(pos))
        Log.debug("New freelist head: %d" % UtmpHead.GetHashHead(0))

        if (Utmp.IsActive(pos)):
            if (Utmp.GetPid(pos) != 0):
                Log.warn("allocating an active utmp!")
                try:
                    os.kill(Utmp.GetPid(pos), signal.SIGHUP)
                except OSError:
                    pass
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
                if (Utmp.IsActive(n) and Utmp.GetPid(n) != 0):
                    try:
                        os.kill(Utmp.GetPid(n), 0)
                    except OSError:
                        username = Utmp.GetUserId(n)
                        Utmp.Clear2(n+1)
                        User.RemoveMsgCount(username)
        UtmpHead.SetReadOnly(1)
        Utmp.Unlock(utmpfd)
#        Log.info("New entry: %d" % pos)
        return pos + 1;

    @staticmethod
    def IsActive(login):
        return Utmp.GetInt(login, UserInfo.ACTIVE_POS)

    @staticmethod
    def GetUserId(login):
        return Utmp.GetString(login, UserInfo.USERID_POS, UserInfo.USERID_SIZE)

    @staticmethod
    def GetUid(login):
        return Utmp.GetInt(login, UserInfo.UID_POS)

    @staticmethod
    def GetPid(login):
        return Utmp.GetInt(login, UserInfo.PID_POS)

    @staticmethod
    def GetInt(login, offset):
        return struct.unpack('=i', Utmp.utmpshm.read(4, login * UserInfo.size + offset))[0]

    @staticmethod
    def GetString(login, offset, size):
        return Util.CString(struct.unpack('=20s', Utmp.utmpshm.read(size, login * UserInfo.size + offset))[0])

    @staticmethod
    def SetUserInfo(pos, userinfo):
        Utmp.utmpshm.write(userinfo.pack(), pos * UserInfo.size)

    @staticmethod
    def Clear(uent, useridx, pid):
        lock = Utmp.Lock()
        Utmp.SetReadOnly(0)

        if (((useridx == 0) or (Utmp.GetUid(uent - 1) == useridx)) and (pid == Utmp.GetPid(uent - 1))):
            Utmp.Clear2(uent);

        Utmp.SetReadOnly(1)
        Utmp.Unlock(lock)

    @staticmethod
    def Clear2(uent):
        pass

    @staticmethod
    def RebuildList():
        pass

