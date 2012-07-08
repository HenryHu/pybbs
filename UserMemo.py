import Config
import os
from Util import Util
import struct
from errors import *
import User
import mmap

class UserMemo:
    parser = struct.Struct('=%ds2s%ds%ds%ds%dscBBB%dsI%ds%ds%ds%ds%ds3si%dsBB2sI%ds%ds%dsBBBBBB%dsB%ds%ds41s44sIi' % (Config.IDLEN + 2, Config.STRLEN - 16, Config.NAMELEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.MOBILE_NUMBER_LEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN, Config.STRLEN))
    _fields = [['userid', 1], '__reserved', ['realemail', 1], ['realname', 1], ['address', 1], ['email', 1], 'gender', 'birthyear', 'birthmonth', 'birthday', ['reg_email', 1], 'mobileregistered', ['mobilenumber', 1], ['OICQ', 1], ['ICQ', 1], ['MSN', 1], ['homepage', 1], 'pad1', 'userface_img', ['userface_url', 1], 'userface_width', 'userface_height', 'pad2', 'group', ['country', 1], ['province', 1], ['city', 1], 'shengxiao', 'bloodtype', 'religion', 'profession', 'married', 'education', ['graduateschool', 1], 'character', ['photo_url', 1], ['telephone', 1], ['smsprefix', 1], ['smsend', 1], 'smsdef', 'signum']
    size = parser.size

    _memo = None
    _name = ""
    def __init__(self, userid, data = None):
        self._name = userid
        if (data is None):
            self.Load()
            self.unpack()
        else:
            self.unpack(data)

    def Load(self):
        fname = User.User.OwnFile(self._name, "usermemo")

        try:
            os.stat(fname)
        except IOError:
            data = self.read()
            if (data is None):
                raise ServerError("can't load usermemo for %s" % self._name)

            try:
                with open(fname, "wb") as f:
                    f.write(data)
            except IOError:
                raise ServerError("can't write usermemo for %s" % self._name)

        try:
            fmemo = open(fname, "r+b")
        except IOError:
            raise ServerError("can't open usermemo for %s" % self._name)

        self._memo = Util.Mmap(fmemo, mmap.PROT_READ | mmap.PROT_WRITE, mmap.MAP_SHARED)
        fmemo.close()
        if (self._memo == None):
            raise ServerError("can't mmap usermemo for %s" % self._name)

        return True

    def read(self):
        datafile = User.User.OwnFile(self._name, ".userdata")
        try:
            with open(datafile, "rb") as f:
                return f.read(self.size)
        except IOError:
            try:
                self.userid = self._name
                data = self.pack(False)
                with open(datafile, "wb") as f:
                    f.write(data)
                return data
            except IOError:
                return None

    def unpack(self, data = None):
        if (data is None):
            Util.Unpack(self, self.parser.unpack(self._memo.read(self.size)))
        else:
            Util.Unpack(self, self.parser.unpack(data))

    def pack(self, write = True):
        if (write):
            self._memo.write(self.parser.pack(*Util.Pack(self)))
        else:
            return self.parser.pack(*Util.Pack(self))

    def GetInfo(self):
        info = {}
        info['userid'] = Util.gbkDec(self.userid)
        info['realemail'] = Util.gbkDec(self.realemail)
        info['realname'] = Util.gbkDec(self.realname)
        info['address'] = Util.gbkDec(self.address)
        info['email'] = Util.gbkDec(self.email)
        info['gender'] = self.gender
        info['birthyear'] = self.birthyear
        info['birthmonth'] = self.birthmonth
        info['birthday'] = self.birthday
        info['reg_email'] = Util.gbkDec(self.reg_email)
        info['mobileregistered'] = self.mobileregistered
        info['mobilenumber'] = Util.gbkDec(self.mobilenumber)
        info['OICQ'] = Util.gbkDec(self.OICQ)
        info['ICQ'] = Util.gbkDec(self.ICQ)
        info['MSN'] = Util.gbkDec(self.MSN)
        info['homepage'] = Util.gbkDec(self.homepage)
        info['userface_img'] = self.userface_img
        info['userface_url'] = Util.gbkDec(self.userface_url)
        info['userface_width'] = self.userface_width
        info['userface_height'] = self.userface_height
        info['group'] = self.group
        info['country'] = Util.gbkDec(self.country)
        info['province'] = Util.gbkDec(self.province)
        info['city'] = Util.gbkDec(self.city)
        info['shengxiao'] = self.shengxiao
        info['bloodtype'] = self.bloodtype
        info['religion'] = self.religion
        info['profession'] = self.profession
        info['married'] = self.married
        info['education'] = self.education
        info['graduateschool'] = Util.gbkDec(self.graduateschool)
        info['character'] = self.character
        info['photo_url'] = Util.gbkDec(self.photo_url)
        info['telephone'] = Util.gbkDec(self.telephone)
        info['smsprefix'] = Util.gbkDec(self.smsprefix)
        info['smsend'] = Util.gbkDec(self.smsend)
        info['smsdef'] = self.smsdef
        info['signum'] = self.signum
        return info

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

