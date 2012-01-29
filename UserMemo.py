class UserMemo:
    _memo = None
    _name = ""
    def __init__(self, userid):
        self._name = userid
        self.Load()

    def Load(self):
        fname = User.OwnFile(self._name, "usermemo")
        fmemo = open(fname, "r+b")
        if (fmemo == None):
            return False

        fstat = os.stat(fname)

        self._memo = Util.Mmap(fmemo, mmap.PROT_READ | mmap.PROT_WRITE, mmap.MAP_SHARED)
        if (self._memo == None):
            fmemo.close()
            return False

        fmemo.close()
        return True

class UserMemoMgr:
    _usermemo_set = {}
    @staticmethod
    def LoadUsermemo(userid):
        if (userid not in UserMemoMgr._usermemo_set):
            usermemo = UserMemoMgr.LoadNewUserMemo(userid)
            if (usermemo == None):
                return None
            UserMemoMgr._usermemo_set[userid] = usermemo
        return UserMemoMgr._usermemo_set[userid]

    @staticmethod
    def LoadNewUserMemo(userid):
        usermemo = UserMemo(userid)
        return usermemo

