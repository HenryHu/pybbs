from Utmp import Utmp
from UtmpHead import UtmpHead
import Config

class Login:
    def __eq__(self, other):
        return (self._loginid == other._loginid)

    def __ne__(self, other):
        return (self._loginid != other._loginid)

    def __init__(self, loginid):
        self._loginid = loginid

    def get_loginid(self):
        return self._loginid

    def get_userid(self):
        return Utmp.GetUserId(self._loginid - 1)

    # UtmpHead.LIST
    @staticmethod
    def list_head():
        listhead = UtmpHead.GetListHead()
        if (listhead == 0):
            return None
        return Login(listhead)

    def list_next(self):
        return Login(UtmpHead.GetListNext(self._loginid - 1))

    def list_prev(self):
        return Login(UtmpHead.GetListPrev(self._loginid - 1))

    def set_listnext(self, listnext):
        return UtmpHead.SetListNext(self._loginid - 1, listnext._loginid)

    def set_listprev(self, listprev):
        return UtmpHead.SetListPrev(self._loginid - 1, listprev._loginid)

    def list_remove(self):
        if (Login.list_head() == self):
            UtmpHead.SetListHead(self.next()._loginid)

        self.list_prev().set_listnext(self.list_next())
        self.list_next().set_listprev(self.list_prev())

    def list_add(self, userid = None):
        if (userid == None):
            userid = self.get_userid()
        if (userid == None or userid == ''):
            raise Exception("illegal call to list_add")

        node = Login.list_head()
        if (node == None):
            # empty list -> single element
            self.set_listprev(self)
            self.set_listnext(self)
            UtmpHead.SetListHead(self._loginid)
            return True

        if (node.get_userid().lower() >= userid.lower()):
            # insert at head
            self.set_listprev(node.list_prev())
            self.set_listnext(node)
            node.set_listprev(self)
            self.list_prev().set_listnext(self)
            UtmpHead.SetListHead(self._loginid)
            return True

        count = 0
        node = node.list_next()
        while ((node.get_userid().lower() < userid.lower()) and (node != Login.list_head())):
            node = node.list_next()
            count += 1
            if (count > Config.USHM_SIZE):
                UtmpHead.SetListHead(0)
                Utmp.RebuildList()
                return False
        self.set_listprev(node.list_prev())
        self.set_listnext(node)
        node.set_listprev(self)
        self.list_prev().set_listnext(self)
        return True

    # UtmpHead.HASH
    @staticmethod
    def hash_head(userid):
        hashkey = Utmp.Hash(userid)
        hashhead = UtmpHead.GetHashHead(hashkey)
        if (hashhead == 0):
            return 0, None
        return hashkey, Login(hashhead)

    def set_hashnext(self, hashnext):
        if (hashnext == None):
            UtmpHead.SetNext(self._loginid - 1, 0)
        else:
            UtmpHead.SetNext(self._loginid - 1, hashnext._loginid)

    def hash_next(self):
        nextid = UtmpHead.GetNext(self._loginid - 1)
        if (nextid == 0):
            return None
        return Login(nextid)

    def hash_remove(self):
        userid = Utmp.GetUserId(self._loginid - 1)
        hashkey, pos = Login.hash_head(userid)
        if (pos == None):
            Log.error("Login.hash_remove: hash list empty!")
            return False
        if (pos.get_loginid() == self.get_loginid()):
            UtmpHead.SetHashHead(hashkey, self.hash_next()._loginid)
        else:
            while (pos.hash_next() != None and pos.hash_next() != self):
                pos = pos.hash_next()
            if (pos.hash_next() == None):
                Log.error("Login.hash_remove: can't find in hash list")
                return False
            else:
                pos.set_hashnext(self.hash_next())

        # add to free list
        self.set_hashnext(Login.free_list())
        Login.set_freelist(self)
        return True

    def hash_add(self, userid = None):
        if (userid == None):
            userid = self.get_userid()
        if (userid == None or userid == ''):
            raise Exception("illegal call to hash_add")

        # remove from free list
        Login.set_freelist(self.hash_next())

        hashkey, node = Login.hash_head(userid)
        self.set_hashnext(node)
        UtmpHead.SetHashHead(hashkey, self._loginid)

    @staticmethod
    def free_list():
        hashhead = UtmpHead.GetHashHead(0)
        if (hashhead == 0):
            return None
        else:
            return Login(hashhead)

    @staticmethod
    def set_freelist(login):
        if (login == None):
            UtmpHead.SetHashHead(0, 0)
        else:
            UtmpHead.SetHashHead(0, login._loginid)


