#!/usr/bin/env python
# coding=utf8

import json
import time
import random
import os
import stat
import socket
import struct

import Config
import modes
import UCache
from Friend import Friend
from Util import Util
from errors import WrongArgs, NoPerm, Unauthorized, NotFound, ServerError
import UserManager
import mail
import BoardManager
import Post
import mailbox
import UserMemo
import Session
from Log import Log

PERM_BASIC =     000001
PERM_CHAT =      000002
PERM_PAGE =      000004
PERM_POST =      000010
PERM_LOGINOK =   000020
PERM_DCS =               000040
PERM_CLOAK =     000100
PERM_SEECLOAK =  000200
PERM_XEMPT =     000400
PERM_WELCOME =   001000
PERM_BOARDS =    002000
PERM_ACCOUNTS =  004000
PERM_CHATCLOAK = 010000
PERM_DENYRELAX =     020000
PERM_SYSOP =     040000
PERM_POSTMASK = 0100000
PERM_ANNOUNCE = 0200000
PERM_OBOARDS =  0400000
PERM_ACBOARD =  01000000
PERM_NOZAP =    02000000
PERM_CHATOP =   04000000
PERM_ADMIN =    010000000
PERM_HORNOR =    020000000
PERM_SECANC =   040000000
PERM_JURY =     0100000000
PERM_SEXY =     0200000000
PERM_CHECKCD =     0200000000
PERM_SUICIDE =  0400000000
PERM_MM =        01000000000
PERM_COLLECTIVE =        01000000000
PERM_DISS =       02000000000
PERM_DENYMAIL =          04000000000
PERM_MALE =                  010000000000

LIFE_DAY_USER =           120
LIFE_DAY_YEAR =          365
LIFE_DAY_LONG =           666
LIFE_DAY_SYSOP =          120
LIFE_DAY_NODIE =          999
LIFE_DAY_NEW =            15
LIFE_DAY_SUICIDE =        3

# these are flags in userec.flags[0] 
PAGER_FLAG   = 0x1  # /* true if pager was OFF last session */
CLOAK_FLAG   = 0x2  # /* true if cloak was ON last session */
BRDSORT_FLAG = 0x20 # /* true if the boards sorted alphabetical */
CURSOR_FLAG  = 0x80 # /* true if the cursor mode open */
GIVEUP_FLAG  = 0x4  # /* true if the user is giving up  by bad 2002.7.6 */
PCORP_FLAG   = 0x40	# /* true if have personalcorp */
#define DEFINE(user,x)     ((x)?((user)->userdefine[def_list(x)])&(x):1)
DEF_ACBOARD    = 000001
DEF_COLOR      = 000002
DEF_EDITMSG    = 000004
DEF_NEWPOST    = 000010
DEF_ENDLINE    = 000020
DEF_LOGFRIEND  = 000040
DEF_FRIENDCALL = 000100
DEF_LOGOUT     = 000200
DEF_INNOTE     = 000400
DEF_OUTNOTE    = 001000
DEF_NOTMSGFRIEND = 002000
DEF_NORMALSCR  = 004000
DEF_CIRCLE     = 010000
DEF_FIRSTNEW   = 020000
DEF_TITLECOLOR = 040000
DEF_ALLMSG     = 0100000
DEF_FRIENDMSG  = 0200000
DEF_SOUNDMSG   = 0400000
DEF_MAILMSG    = 01000000
DEF_LOGININFORM= 02000000
DEF_SHOWSCREEN = 04000000
DEF_SHOWHOT    = 010000000
DEF_NOTEPAD    = 020000000
DEF_IGNOREMSG  = 040000000   #   /* Added by Marco */
DEF_HIGHCOLOR = 0100000000   #/*Leeward 98.01.12 */
DEF_SHOWSTATISTIC = 0200000000 #   /* Haohmaru */
DEF_UNREADMARK = 0400000000    #   /* Luzi 99.01.12 */
DEF_USEGB   = 01000000000   #    /* KCN,99.09.05 */
DEF_CHCHAR  = 02000000000
DEF_SHOWDETAILUSERDATA = 04000000000
DEF_SHOWREALUSERDATA  = 010000000000
DEF_HIDEIP                    = 040000000001

#//DEF_SPLITSCREEN 02000000000 /* bad 2002.9.1 */
ALL_PAGER = 0x1
FRIEND_PAGER = 0x2
ALLMSG_PAGER = 0x4
FRIENDMSG_PAGER = 0x8

class User:
    name = ''
    userec = None

    def __init__(self, user, userec, umemo):
        self.name = user
        self.userec = userec
        self.memo = umemo
        self.mbox = mailbox.MailBox(user)

    @staticmethod
    def POST(svc, session, params, action):
        if (action == 'login'):
            if (not (params.has_key('name') and (params.has_key('pass')))):
                raise WrongArgs('lack of username or password')

            raise NoPerm("normal login disabled, please use OAuth")
            UserManager.UserManager.HandleLogin(svc, params['name'], params['pass'])
        elif action == 'register':
            User.Register(svc, params)
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')
        if (action == 'query'):
            userid = svc.get_str(params, 'id', '')
            if not session.CheckScope('bbs'):
                if userid or not session.CheckScope('auth'):
                    raise NoPerm("out of scope")
            if (not userid):
                userid = session.GetUser().name
            User.QueryUser(svc, userid)
        elif (action == 'detail'):
            if not session.CheckScope('bbs'): raise NoPerm("out of scope")
            userid = svc.get_str(params, 'id', '')
            if (not userid):
                userid = session.GetUser().name
            else:
                if (not session.GetUser().IsSysop()):
                    raise NoPerm("permission denied")
            User.DetailUser(svc, userid)
        elif (action == "signature_id"):
            if not session.CheckScope('bbs'): raise NoPerm("out of scope")
            sigid = session.GetUser().GetSigID()
            svc.writedata(json.dumps({"signature_id" : sigid}))
        elif action == "signature_count":
            if not session.CheckScope('bbs'): raise NoPerm("out of scope")
            sig_count = session.GetUser().GetSignatureCount()
            svc.writedata(json.dumps({"signature_count" : sig_count}))
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def OwnFile(userid, str):
        return os.path.join(User.HomePath(userid), str)

    def MyFile(self, str):
        return User.OwnFile(self.name, str)

    @staticmethod
    def CacheFile(userid, str):
        return os.path.join(Config.BBS_ROOT, "cache", "home", userid[0].upper(),
                userid, str)

    @staticmethod
    def HomePath(userid):
        return os.path.join(Config.BBS_ROOT, "home", userid[0].upper(), userid)

    def Authorize(self, password):
        return (Util.HashGen(password, self.name) == self.userec.md5passwd and
            self.HasPerm(PERM_BASIC))

    def HasPerm(self, perm):
        if (perm == 0):
            return True
        if (self.userec.userlevel & perm != 0):
            return True
        return False

    def IsSysop(self):
        return self.HasPerm(PERM_SYSOP)

    def IsBM(self):
        return self.HasPerm(PERM_BOARDS)

    def IsSuperBM(self):
        return self.HasPerm(PERM_OBOARDS)

    def IsDigestMgr(self):
        return self.HasPerm(PERM_ANNOUNCE)

    def IsSECANC(self):
        # 'special permission 5' 'BM: ZIXIAs'
        return self.HasPerm(PERM_SECANC)

    def IsSuicider(self):
        return self.HasPerm(PERM_SUICIDE)

    def CanMail(self):
        return not self.HasPerm(PERM_DENYMAIL)

    def ClearPerm(self, perm):
        self.userec.userlevel &= ~perm

    def HasFlag(self, flag):
        if (self.userec.flags & flag != 0):
            return True
        return False

    @staticmethod
    def DefinePos(value):
        if (value < DEF_HIDEIP):
            return 0
        return 1

    def Defined(self, value):
        if (value == 0):
            return True
        if (self.userec.userdef[User.DefinePos(value)] & value != 0):
            return True
        return False

    def Define(self, value):
        self.userec.userdef[User.DefinePos(value)] |= value

    def Undef(self, value):
        self.userec.userdef[User.DefinePos(value)] &= ~value

    def CanReadClub(self, clubnum):
        idx = clubnum - 1
        if (self.userec.club_read_rights[idx >> 5] & (1 << (idx & 0x1f)) != 0):
            return True
        return False

    def CanPostClub(self, clubnum):
        idx = clubnum - 1
        if (self.userec.club_write_rights[idx >> 5] & (1 << (idx & 0x1f)) != 0):
            return True
        return False

    def GetTitle(self):
        return self.userec.title

    def CanSendTo(self, userinfo):
        # can I send to userinfo?
        if (userinfo.mode == modes.LOCKSCREEN):
            return False
        if (userinfo.AcceptMsg() or self.HasPerm(PERM_SYSOP)):
            return True
        if (userinfo.AcceptMsg(True)):
            return userinfo.HasFriend(UCache.UCache.SearchUser(self.userec.userid))[0]
        return False

    @staticmethod
    def InvalidId(username):
        if (username.isalpha()):
            return False
        return True

    def GetFriends(self, userinfo):
        userinfo.friendsnum = 0
        path = self.MyFile("friends")
        numFriends = Util.GetRecordCount(path, Friend.size)
#        Log.info("numFriends: %d" % numFriends)
        if (numFriends <= 0):
            return 0
        if (numFriends > Config.MAXFRIENDS):
            numFriends = Config.MAXFRIENDS

        friends = map(Friend, Util.GetRecords(path, Friend.size, 1, numFriends))
        i = 0
        while (True):
            if (i >= numFriends):
                break
#            Log.debug("checking %d %s %d" % (i, friends[i].id, -1 if User.InvalidId(friends[i].id) else UCache.UCache.SearchUser(friends[i].id)))
            if (User.InvalidId(friends[i].id) or UCache.UCache.SearchUser(friends[i].id) == 0):
#                Log.debug("removing %d %s" % (i, friends[i].id))
                friends[i] = friends[numFriends - 1]
                numFriends = numFriends - 1
                friends.pop()
                i = i - 1
#            print i,numFriends,len(friends)

            i = i + 1

        friends.sort(key = Friend.NCaseId)

        userinfo.friends_nick = []
        for i in range(numFriends):
#            Log.debug("friend %d %s" % (i, friends[i].id))
            userinfo.friends_uid[i] = UCache.UCache.SearchUser(friends[i].id)
            userinfo.friends_nick.append(friends[i].exp)

        userinfo.friendsnum = numFriends
        return 0

    @staticmethod
    def RemoveMsgCount(username):
        pass

    def BeIgnored(self, userid):
        if (self.HasPerm(PERM_SYSOP)):
            return False
        ignores = User.OwnFile(userid, 'ignores')
        itemcount = Util.GetRecordCount(ignores, Config.IDLEN + 1)
        if (itemcount == -1):
            return False
        records = Util.GetRecords(ignores, Config.IDLEN + 1, 1, itemcount)
        for guy in records:
            if (Util.CString(guy).lower() == self.name.lower()):
                return True
        return False

    def CanSee(self, userinfo):
        return (self.HasPerm(PERM_SEECLOAK) or
                not userinfo.invisible or
                userinfo.userid == self.name)

    def IsOwner(self, post):
        if self.name != post.owner and self.name != post.realowner:
            return False
        posttime = post.GetPostTime()
        if posttime < self.userec.firstlogin:
            return False
        return True

    def AddNumPosts(self):
        self.userec.numposts += 1

    def DecNumPosts(self):
        if self.userec.numposts > 0:
            self.userec.numposts -= 1

    def ComputeLife(self):
        if ((self.HasPerm(PERM_XEMPT) or self.HasPerm(PERM_CHATCLOAK)) and not self.HasPerm(PERM_SUICIDE)):
            return LIFE_DAY_NODIE;

        if (self.HasPerm(PERM_ANNOUNCE) or self.HasPerm(PERM_OBOARDS)):
            return LIFE_DAY_SYSOP;

        value = (int(time.time()) - self.userec.lastlogin) / 60
        if (value == 0):
            value = 1

        if (self.name == "new"):
            # maybe one day, we can register new user...
            # but, "new"?....
            return (LIFE_DAY_NEW - value) / 60

        day_min = 60 * 24
        if (self.HasPerm(PERM_SUICIDE) or self.userec.numlogins <= 3):
            return (LIFE_DAY_SUICIDE * day_min - value) / day_min

        if (not self.HasPerm(PERM_LOGINOK)):
            return (LIFE_DAY_NEW * day_min - value) / day_min

        return ((LIFE_DAY_USER + 1) * day_min - value) / day_min

    def ComputePerf(self):
        if (self.name == "guest"):
            return -9999

        reg_days = (int(time.time()) - self.userec.firstlogin) / 86400 + 1
        perf = int((1. * self.userec.numposts / self.userec.numlogins + 1. * self.userec.numlogins / reg_days) * 10)
        if (perf < 0):
            perf = 0
        return perf

    def ComputeExp(self):
        if (self.name == "guest"):
            return -9999

        reg_days = (int(time.time()) - self.userec.firstlogin) / 86400
        exp = self.userec.numposts + self.userec.numlogins / 5 + reg_days + self.userec.stay / 3600
        if (exp < 0):
            exp = 0
        return exp

    def GetInfo(self):
        info = {}
        info['userid'] = Util.gbkDec(self.name)
        info['nick'] = Util.gbkDec(self.userec.username)
        info['numlogins'] = self.userec.numlogins
        info['numposts'] = self.userec.numposts
        info['lastlogintime'] = time.ctime(self.userec.lastlogin)
        info['lastlogin'] = self.userec.lastlogin
        info['lasthost'] = self.userec.lasthost
        info['exp'] = self.ComputeExp()
        info['perf'] = self.ComputePerf()
        info['life'] = self.ComputeLife()
        plan = self.GetPlan()
        if (plan is not None):
            info['plan'] = plan
        info['unread_mail'] = mail.Mail.CheckUnread(self)

        return info

    def GetPlan(self):
        plan_file = self.MyFile("plans")
        try:
            with open(plan_file, "r") as f:
                return Util.gbkDec(f.read())
        except IOError:
            return None

    def RecordLogin(self, fromip, userinfo, count):
        if (userinfo is None or not userinfo.invisible):
            self.userec.lasthost = fromip
            self.userec.lastlogin = int(time.time())
            if (count):
                self.userec.numlogins += 1

        if (self.userec.numlogins < 1):
            self.userec.numlogins = 1
        if (self.userec.numposts < 0):
            self.userec.numposts = 0
        if (self.userec.stay < 0):
            self.userec.stay = 1
        # login? so you still want to live...
        self.ClearPerm(PERM_SUICIDE)
        if (self.userec.firstlogin == 0):
            self.userec.firstlogin = int(time.time()) - 7 * 86400

    @staticmethod
    def QueryUser(svc, userid):
        user = UserManager.UserManager.LoadUser(userid)
        if (user is None):
            raise NotFound("user %s not found" % userid)
        info = user.GetInfo()
        svc.writedata(json.dumps(info))

    @staticmethod
    def DetailUser(svc, userid):
        user = UserManager.UserManager.LoadUser(userid)
        if (user is None):
            raise NotFound("user %s not found" % userid)
        info = user.memo.GetInfo()
        svc.writedata(json.dumps(info))

    def GetSignatureCount(self):
        return self.memo.signum

    def SetSigID(self, sigid):
        self.userec.signature = sigid

    def GetSigID(self):
        return self.userec.signature

    def GetName(self):
        return self.name

    def GetUID(self):
        return self.userec.GetUID()

    def CanMailTo(self, receiver):
        if self.IsSysop() or self.name == "Arbitrator":
            return 'ok'
        if receiver.IsSuicider():
            return 'suicide'
        if self.MailboxFull():
            return 'full'
        if receiver.MailboxFull():
            return 'recvfull'
        return 'ok'

    def MayMailTo(self, receiver):
        if not self.CanMail():
            raise NoPerm("you don't have permission to mail")

        if self.BeIgnored(receiver.name):
            raise NoPerm("you're denied by user '%s'" % receiver.name)

        result = self.CanMailTo(receiver)
        if result != 'ok':
            if result == 'suicide':
                raise WrongArgs("fail to send to '%s'" % receiver.name)
            if result == 'full':
                raise NoPerm("your mailbox is full")
            if result == 'recvfull':
                raise WrongArgs("his mailbox is full")
            raise WrongArgs("fail to send mail")
        return True

    def SendMailTo(self, receiver_id, title, content, signature_id, session,
            save_in_sent):
        receiver = UserManager.UserManager.LoadUser(receiver_id)
        if receiver is None:
            raise NotFound("no such user '%s'" % receiver_id)

        if not self.MayMailTo(receiver):
            raise NoPerm("no permission") # not reachable

        header = Post.Post.PrepareHeaderForMail(self, title, session)
        signature = Util.gbkDec(self.GetSig(signature_id))

        content = header + content + signature

        self.MailTo(receiver, title, content, save_in_sent)

    def MailTo(self, receiver, title, content, save_in_sent):
        mbox = receiver.mbox
        mail_size = mbox.new_mail(self, title, content)
        receiver.AddUsedSpace(mail_size)

        if save_in_sent:
            mail_size = self.mbox.new_sent_mail(receiver, title, content)
            self.AddUsedSpace(mail_size)

        # TODO: mark mail available

        if receiver.name == "SYSOP":
            board = BoardManager.BoardManager.GetBoard(Config.SYSMAIL_BOARD)
            board.UpdateLastPost()

    def AddUsedSpace(self, space):
        self.userec.usedspace += space

    def GetSig(self, sig):
        result = ""
        self.SetSigID(sig)
        if (sig == 0):
            return result

        if (sig < 0):
            signum = self.GetSignatureCount()
            if (signum == 0):
                sig = 0
            else:
                sig = random.randint(1, signum)

        sig_fname = self.MyFile("signatures")
        valid_ln = 0
        tmpsig = []
        # hack: c code limit the size of buf
        # we must follow this, or the line number would be different
        # fgets(256) = readline(255)
        buf_size = 255
        try:
            with open(sig_fname, "r") as sigfile:
                result += '\n--\n'
                for i in xrange(0, (sig - 1) * Config.MAXSIGLINES):
                    line = sigfile.readline(buf_size)
                    if (line == ""):
                        return result
                for i in range(0, Config.MAXSIGLINES):
                    line = sigfile.readline(buf_size)
                    if (line != ""):
                        if (line[0] != '\n'):
                            valid_ln = i + 1
                        tmpsig += [line]
                    else:
                        break
        except IOError:
            Log.error("Post.AddSig: IOError on %s" % sig_fname)

        result += ''.join(tmpsig[:valid_ln])
        return result

    def MailboxFull(self):
        if Config.MAIL_SIZE_LIMIT != mail.MAIL_SIZE_UNLIMITED:
            if self.userec.usedspace > Config.MAIL_SIZE_LIMIT:
                return True
            if self.mbox.full():
                return True
        return False

    @staticmethod
    def IsInvalidId(username):
        return not username.isalpha()

    @staticmethod
    def IsBadId(username):
        username = username.lower()
        if username == "deliver" or username == "new":
            return True
        for ch in username:
            if not ch.isalnum() and ch != '_':
                return True
        if len(username) < 2:
            return True
        try:
            with open(os.path.join(Config.BBS_ROOT, '.badname'), 'r') as badf:
                line = badf.readline()
                while line:
                    line = line.strip()
                    if line[:1] != '#':
                        parts = line.split()
                        if len(parts) == 1 and parts[0] == username:
                            return True
                        if len(parts) == 2 and parts[0] == username:
                            if time.time() - int(parts[1]) <= 24 * 30 * 3600:
                                return True

                    line = badf.readline()
        except:
            pass
        return False

    def SetPasswd(self, passwd):
        self.userec.md5passwd = Util.HashGen(passwd, self.name)

    @staticmethod
    def GetNewUserId(username):
        try:
            sock = socket.create_connection(('127.0.0.1', 60001))
            sock.sendall("NEW %s" % username)
            ret = sock.recv(4)
            if len(ret) == 4:
                newid = struct.unpack('=i', ret)[0]
                Log.debug("new user id: %d" % newid)
                return newid
            Log.error("invalid response from miscd for newuser")
            return -1
        except Exception as exc:
            Log.error("fail to get new user id: %r" % exc)
            return -1

    @staticmethod
    def Register(svc, params):
        username = svc.get_str(params, 'username')
        password = svc.get_str(params, 'password')
        if len(password) < 4:
            raise WrongArgs("password too short")
        if password == username:
            raise WrongArgs("password equals to username")
        if User.IsInvalidId(username):
            raise WrongArgs("invalid id")
        if len(username) < 2:
            raise WrongArgs("id too short")
        if User.IsBadId(username):
            raise WrongArgs("bad id")
        if UCache.UCache.SearchUser(username) != 0:
            raise WrongArgs("user exists")

        # detailed info
        nick = svc.get_str(params, 'nick').decode('utf-8')
        if len(nick) < 2:
            raise WrongArgs("nick too short")

        email = svc.get_str(params, 'email').decode('utf-8')
        if not Util.IsValidEmail(email):
            raise WrongArgs("invalid email")
        realname = svc.get_str(params, 'realname').decode('utf-8')
        if len(realname) < 2:
            raise WrongArgs("realname too short")
        address = svc.get_str(params, 'address').decode('utf-8')
        if len(address) < 6:
            raise WrongArgs("address too short")
        birthyear = svc.get_int(params, 'birthyear')
        birthmonth = svc.get_int(params, 'birthmonth')
        birthday = svc.get_int(params, 'birthday')
        if not Util.IsValidDate(birthyear, birthmonth, birthday):
            raise WrongArgs("invalid birth day")
        gender = svc.get_str(params, 'gender').upper()
        if gender != "M" and gender != "F":
            raise WrongArgs("invalid sex")
        selfintro = svc.get_str(params, 'selfintro', '').decode('utf-8')
        if len(selfintro) > Config.SELF_INTRO_MAX_LEN:
            # way too long!
            selfintro = selfintro[:Config.SELF_INTRO_MAX_LEN]
        # registry form info
        phone = svc.get_str(params, 'phone').decode('utf-8')
        career = svc.get_str(params, 'career').decode('utf-8')

        # check home directory
        homepath = User.HomePath(username)
        try:
            st = os.stat(homepath)
            if not stat.S_ISDIR(st.st_mode):
                raise WrongArgs("fail to create home dir")
            if time.time() - st.st_ctime < Config.SEC_DELETED_OLDHOME:
                raise WrongArgs("recently registered")
        except OSError:
            pass

        # check for registry form
        try:
            with open(os.path.join(Config.BBS_ROOT, "new_register"), "r") as forms:
                line = forms.readline()
                while line:
                    line = line.strip()
                    if line == "userid: " + username:
                        raise WrongArgs("registry form exists")
                    line = forms.readline()
        except WrongArgs as e:
            raise e
        except:
            pass

        # CHANGE BEGIN
        try:
            os.mkdir(User.HomePath(username), 0755)
        except:
            raise ServerError("fail to create home dir")

        # fill in new user data
        newuser = UCache.UCache.CreateUserRecord(username)
        newusermemo = UserMemo.UserMemo(username)
        newuserobj = User(username, newuser, newusermemo)

        newuser.firstlogin = newuser.lastlogin = int(time.time() - 13 * 60 *24)
        newuserobj.SetPasswd(password)
        # set new user's level to 0, so he can't login
        newuser.userlevel = 0
        newuser.userdef[0] = -1
        newuser.userdef[1] = -1
        newuserobj.Undef(DEF_NOTMSGFRIEND)
        newuser.notemode = -1
        newuser.exittime = int(time.time() - 100)
        newuser.flags = CURSOR_FLAG | PAGER_FLAG
        newuser.title = 0
        # ????
        newuser.firstlogin = newuser.lastlogin = int(time.time())

        # 2nd part: detailed info
        newuser.username = Util.gbkEnc(nick)
        # set it to 1, so it will send hello email again
        newuser.numlogins = 1
        newuser.lasthost = svc.address_string()

        allocid = User.GetNewUserId(username)
        if allocid > Config.MAXUSERS or allocid <= 0:
            raise ServerError("no more users")
        newuser.Allocate(allocid)

        if UCache.UCache.SearchUser(username) == 0:
            raise ServerError("failed to create user")

        # clear old cache
        cachepath = User.CacheFile(username, "entry")
        try:
            os.remove(cachepath)
        except:
            pass

        # TODO: log

        # login check part
        newusermemo.realname = Util.gbkEnc(realname)
        newusermemo.address = Util.gbkEnc(address)
        newusermemo.gender = gender
        newusermemo.birthyear = birthyear - 1900
        newusermemo.birthmonth = birthmonth
        newusermemo.birthday = birthday
        newusermemo.email = Util.gbkEnc(email)
        newusermemo.pack()
        newusermemo.write_data()
        newusermemo.close()

        # TODO: convey ID
        # TODO: SYSOP register

        # post newcomers email
        newmail = u"""大家好,\n
我是 %s (%s), 来自 %s
今天%s初来此站报到, 请大家多多指教。
""" % (username, nick, svc.address_string(), u"小弟" if gender == 'M' else u"小女子")
        if selfintro:
            newmail += u"\n\n自我介绍:\n\n%s" % selfintro
        newboard = BoardManager.BoardManager.GetBoard("newcomers")
        title = u"新手上路: %s" % nick
        fakesession = Session.BasicSession(svc.address_string())
        newboard.PostArticle(newuserobj, title, newmail, None, 0, False, False,
                fakesession, None, True)

        # add new registry form
        with open(os.path.join(Config.BBS_ROOT, "new_register"), 'a') as regf:
            regf.write("usernum: %d, %s\n" % (allocid, time.ctime()))
            regf.write("userid: %s\n" % username)
            regf.write(Util.gbkEnc(u"realname: %s\n" % realname))
            regf.write(Util.gbkEnc(u"career: %s\n" % career))
            regf.write(Util.gbkEnc(u"addr: %s\n" % address))
            regf.write(Util.gbkEnc(u"phone: %s\n" % phone))
            regf.write("birth: %d-%d-%d\n" % (
                birthyear - 1900, birthmonth, birthday))
            regf.write("----\n")

        svc.writedata(json.dumps({"result": "ok"}))

