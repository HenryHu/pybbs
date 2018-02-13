import Config
import os
import struct
import random
import time
import signal
import User
import UCache
from sysv_ipc import *
from UtmpHead import UtmpHead
from commondata import CommonData
from UserInfo import UserInfo
from Log import Log
from Util import Util
import Login
# from SemLock import SemLock

UTMPFILE_SIZE = UserInfo.size * Config.USHM_SIZE
UTMPHEAD_SIZE = 4 * Config.USHM_SIZE + 4 * (Config.UTMP_HASHSIZE + 1) + 4 * 3 + 8 * Config.USHM_SIZE

class Utmp:
    utmpshm = None

    @staticmethod
    def Init():
        if (Utmp.utmpshm == None):
            try:
                Log.info("attaching to UTMP shared memory")
                Utmp.utmpshm = SharedMemory(Config.Config.GetInt("UTMP_SHMKEY", 3699), size = UTMPFILE_SIZE)
                Log.info("attaching to UTMPHEAD shared memory")
                UtmpHead.utmphead = SharedMemory(Config.Config.GetInt("UTMPHEAD_SHMKEY", 3698), size = UTMPHEAD_SIZE);
            except ExistentialError:
                Log.info("Creating UTMP shared memory")
                Utmp.utmpshm = SharedMemory(Config.Config.GetInt("UTMP_SHMKEY", 3699), size = UTMPFILE_SIZE, flags = IPC_CREAT, mode = 0660, init_character='\0')
                Log.info("Creating UTMPHEAD shared memory")
                UtmpHead.utmphead = SharedMemory(Config.Config.GetInt("UTMPHEAD_SHMKEY", 3698), size = UTMPHEAD_SIZE, flags = IPC_CREAT, mode = 0660, init_character='\0')
                Utmp.ResetUtmp()
            Log.info("Utmp initialization finished")
        else:
            Log.info("Utmp already initialized")

    @staticmethod
    def ResetUtmp(locked=False):
        Log.info("Initializing UTMPHEAD shared memory")
        if not locked:
            fd = Utmp.Lock()
        UtmpHead.SetNumber(0)
        UtmpHead.SetHashHead(0, 1)
        UtmpHead.SetListHead(0)
        for i in range(Config.USHM_SIZE - 1):
            UtmpHead.SetNext(i, i+2)
        UtmpHead.SetNext(Config.USHM_SIZE - 1, 0)
        if not locked:
            Utmp.Unlock(fd)

    @staticmethod
    def Hash(userid):
        hash = UCache.UCache.Hash(userid)
        if (hash == 0):
            return 0
        hash = (hash / 3) % Config.UTMP_HASHSIZE
        if (hash == 0):
            return 1
        return hash

    @staticmethod
    def Lock():
        #try:
            #SemLock.Lock(Config.UCACHE_SEMLOCK, timeout = 10);
            #return 0;
        #except BusyError:
            #return -1;
#        Log.debug("Utmp.Lock enter()")
        lockf = os.open(Config.BBS_ROOT + "UTMP", os.O_RDWR | os.O_CREAT, 0600)
        if (lockf < 0):
            Log.error("Fail to open lock file!")
            raise Exception("fail to lock!")
        Util.FLock(lockf, shared = False)
#        Log.debug("Utmp.Lock succ()")
        return lockf

    @staticmethod
    def Unlock(lockf):
        #SemLock.Unlock(Config.UCACHE_SEMLOCK)
#        Log.debug("Utmp.Unlock")
        Util.FUnlock(lockf)
        os.close(lockf)

    @staticmethod
    def GetNewUtmpEntry(userinfo):
        utmpfd = Utmp.Lock()
        pos = -2
        try:
            UtmpHead.SetReadOnly(0)

            userinfo.utmpkey = random.randint(0, 99999999);
            pos = UtmpHead.GetHashHead(0) - 1;
            Log.debug("New entry: %d" % (pos + 1))
            if (pos == -1):
                UtmpHead.SetReadOnly(1)
                Log.error("Utmp full!")
                raise Exception("Utmp full!")

            login = Login.Login(pos + 1)
            if (not login.list_add(userinfo.userid)):
                UtmpHead.SetReadOnly(1)
                Log.error("Utmp list loop!")
                raise Exception("Utmp list loop!")
            login.hash_add(userinfo.userid)

        #if (UtmpHead.GetListHead() == 0):
            #UtmpHead.SetListPrev(pos, pos+1)
            #UtmpHead.SetListNext(pos, pos+1)
            #UtmpHead.SetListHead(pos+1)
        #else:
            #i = UtmpHead.GetListHead()
            #if (Utmp.GetUserId(i-1).lower() >= userinfo.userid.lower()):
                #UtmpHead.SetListPrev(pos, UtmpHead.GetListPrev(i-1))
                #UtmpHead.SetListNext(pos, i)
                #UtmpHead.SetListPrev(i-1, pos+1)
                #UtmpHead.SetListNext(UtmpHead.GetListPrev(pos) - 1, pos+1)
                #UtmpHead.SetListHead(pos+1)
            #else:
                #count = 0;
                #i = UtmpHead.GetListNext(i-1)
                #while ((Utmp.GetUserId(i-1).lower() < userinfo.userid.lower()) and (i != UtmpHead.GetListHead())):
                    #i = UtmpHead.GetListNext(i-1)
                    #count = count + 1;
                    #if (count > Config.USHM_SIZE):
                        #UtmpHead.SetListHead(0)
                        #Utmp.RebuildList()
                        #UtmpHead.SetReadOnly(1)
                        #Utmp.Unlock(utmpfd)
                        #Log.error("Utmp list loop!")
                        #return -1 # wrong! exit(-1)!
                #UtmpHead.SetListPrev(pos, UtmpHead.GetListPrev(i-1))
                #UtmpHead.SetListNext(pos, i)
                #UtmpHead.SetListPrev(i-1, pos+1)
                #UtmpHead.SetListNext(UtmpHead.GetListPrev(pos) - 1, pos+1)
#        UtmpHead.SetHashHead(0, UtmpHead.GetNext(pos))
#        Log.debug("New freelist head: %d" % UtmpHead.GetHashHead(0))

            if (Utmp.IsActive(pos)):
                if (Utmp.GetPid(pos) != 0):
                    Log.warn("allocating an active utmp!")
                    try:
                        os.kill(Utmp.GetPid(pos), signal.SIGHUP)
                    except OSError:
                        pass
            userinfo.SetIndex(pos + 1)
            userinfo.save()
#        Utmp.SetUserInfo(pos, userinfo)
#        hashkey = Utmp.Hash(userinfo.userid)

#        i = UtmpHead.GetHashHead(hashkey);
#        UtmpHead.SetNext(pos, i)
#        UtmpHead.SetHashHead(hashkey, pos+1)

            UtmpHead.IncNumber()
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
                            User.User.RemoveMsgCount(username)
            UtmpHead.SetReadOnly(1)
        finally: # lock is important!
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
        return Util.CString(Utmp.utmpshm.read(size, login * UserInfo.size + offset))

    @staticmethod
    def SetUserInfo(pos, userinfo):
        Utmp.utmpshm.write(userinfo.pack(), pos * UserInfo.size)

    @staticmethod
    def Clear(uent, useridx, pid):
        lock = Utmp.Lock()
        try:
            UtmpHead.SetReadOnly(0)

            if (((useridx == 0) or (Utmp.GetUid(uent - 1) == useridx)) and (pid == Utmp.GetPid(uent - 1))):
                Utmp.Clear2(uent);

            UtmpHead.SetReadOnly(1)
        finally: # lock is important!
            Utmp.Unlock(lock)

    @staticmethod
    def Clear2(uent):
        userinfo = UserInfo(uent)

        Log.debug("clearing user %s uid %d loginid %d" % (userinfo.userid, userinfo.uid, uent))
        user = UCache.UCache.GetUserByUid(userinfo.uid)
        UCache.UCache.DoAfterLogout(user, userinfo, uent, 0)

        login = Login.Login(uent)
        login.hash_remove()
        login.list_remove()

        if (userinfo.active):
            UtmpHead.DecNumber()

        Log.debug("zeroing utmp %d" % uent)
        zeroinfo = UserInfo()
        zeroinfo.SetIndex(uent)
        zeroinfo.save()

    @staticmethod
    def RebuildList():
        lock = Utmp.Lock()
        try:
            entries = []
            hashes = {}
            active = set()
            for i in xrange(Config.USHM_SIZE):
                userinfo = UserInfo(i + 1)
                if userinfo.active == 1:
                    entries.append((i, userinfo.userid))
                    hash = Utmp.Hash(userinfo.userid)
                    hashes[hash] = hashes.get(hash, []) + [i]
                    active.add(i)

            if entries == []:
                Log.info("NO USER! RESET!")
                Utmp.ResetUtmp(locked=True)
            else:
                cnt = len(entries)
                Log.info("Rebuild Utmp with %d entries" % cnt)
                entries.sort(key=lambda entry: entry[1])
                UtmpHead.SetReadOnly(0)

                # rebuild list
                UtmpHead.SetListHead(entries[0][0] + 1)
                for i in xrange(len(entries)):
                    pos = entries[i][0]
                    next = entries[(i + 1) % cnt][0]
                    prev = entries[(i - 1 + cnt) % cnt][0]
                    UtmpHead.SetListNext(pos, next + 1)
                    UtmpHead.SetListPrev(pos, prev + 1)
                    print pos, "prev", prev, "next", next

                # rebuild hash
                for hash in hashes:
                    cnt = len(hashes[hash])
                    UtmpHead.SetHashHead(hash, hashes[hash][0] + 1)
                    print "hash", hash, "head", hashes[hash][0]
                    for i in xrange(cnt):
                        pos = hashes[hash][i]
                        if i < cnt - 1:
                            next = hashes[hash][i + 1]
                        else:
                            next = -1
                        UtmpHead.SetNext(pos, next + 1)
                        print "next", pos, next
                for i in xrange(Config.UTMP_HASHSIZE):
                    if i != 0 and UtmpHead.GetHashHead(i) != 0 and not i in hashes:
                        UtmpHead.SetHashHead(i, 0)
                        print "reset", i

                # TODO: rebuild free list at hash[0]

                #if min(active) > 0:
                #    UtmpHead.SetHashHead(0, 1)

                UtmpHead.SetReadOnly(1)
        finally:
            Utmp.Unlock(lock)

