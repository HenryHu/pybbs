from sysv_ipc import *
import Config

class SemLock:
    sems = None

    @staticmethod
    def Init():
        semkey = Config.Config.GetInt("PUBLIC_SEMID", 0x54188)
        try:
            sems = [Semaphore(semkey)]
        except ExistentialError:
            sems = [Semaphore(semkey, flags = IPC_CREAT | IPC_EXCL, mode = 0700)];
            for i in range(len(sems)):
                sems[i].release()

    @staticmethod
    def Lock(lockid, timeout = None):
        if (SemLock.sems == None):
            SemLock.Init()
        if (lockid != 0):
            Log.error("Invalid lockid!")
            lockid = 0
        SemLock.sems[lockid].acquire(timeout)

    @staticmethod
    def Unlock(lockid):
        if (SemLock.sems == None):
            SemLock.Init()
        if (lockid != 0):
            Log.error("Invalid lockid!")
            lockid = 0
        SemLock.sems[lockid].release()


