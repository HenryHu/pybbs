#!/usr/bin/env python
import os
import copy
import signal
import time

from Log import Log
import User
import UserManager
import Config
import MsgBox
import MsgHead
import modes

class Msg:
    @staticmethod
    def SaveMsg(from_userid, to_userid, to_pid, text_body, sender_mode = 4):
        to_msgbox = MsgBox.MsgBox(to_userid)

        from_msgbox = MsgBox.MsgBox(from_userid)

        to_msg = MsgHead.MsgHead()
        to_msg.time = int(time.time())
        to_msg.sent = 0
        to_msg.mode = sender_mode
        to_msg.id = from_userid
        to_msg.frompid = os.getpid()
        to_msg.topid = to_pid

        from_msg = copy.copy(to_msg)
        from_msg.sent = 1
        from_msg.id = to_userid

        if (to_msgbox.SaveMsgText(to_msg, text_body) < 0):
            return -21
        if (to_userid != from_userid and sender_mode != 3):
            if (from_msgbox.SaveMsgText(from_msg, text_body) < 0):
                return -21

        return 1

    @staticmethod
    def NotifyMsg(from_userid, to_userid, to_userinfo):
        if (to_userinfo.mode == modes.WWW):
            to_userinfo.mailcheck |= UserInfo.CHECK_MSG
            to_userinfo.save()
            return 1

        if (to_userinfo.pid != 1 
                and to_userinfo.mode != modes.MSG 
                and to_userinfo.mode != modes.LOCKSCREEN):
            try:
                os.kill(to_userinfo.pid, signal.SIGUSR2)
            except OSError:
                return -13
        return 1
 
    @staticmethod
    def MaySendMsg(from_userid, to_userid, to_userinfo, sender_mode = 4):
        from_user = UserManager.UserManager.LoadUser(from_userid)

        if (not from_user.HasPerm(User.PERM_SEECLOAK) 
                and to_userinfo.invisible 
                and from_userid != to_userid 
                and sender_mode != modes.CHAT1):
            return -2

        if (to_userinfo.mode == modes.LOCKSCREEN and sender_mode != 3):
            return -1

        if (from_user.BeIgnored(to_userid) and sender_mode != 3):
            return -11

        to_msgbox = MsgBox.MsgBox(to_userid)
        if (to_userinfo.mode != modes.WEBEXPLORE and sender_mode != 3):
            if (to_msgbox.GetUnreadCount() > Config.MAXMESSAGE):
                return -12;

        to_userinfo.load()
        if (to_userinfo.active == 0 or to_userinfo.pid == 0 or to_userinfo.userid != to_userid):
            Log.debug("error -14: %d %d %s" % (to_userinfo.active, to_userinfo.pid, to_userinfo.userid))
            return -14;

        try:
            os.kill(to_userinfo.pid, 0)
        except OSError:
            Log.debug("error -14: kill fail")
            return -14

        return 1

