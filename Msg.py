#!/usr/bin/env python
import os
import copy
import signal

import User
import UserManager
import MsgBox
import MsgHead
import modes

class Msg:
    @staticmethod
    def SendMsg(from_userid, to_userid, to_userinfo, text_body, sender_mode = modes.XMPP):
        from_user = UserManager.UserManager.LoadUser(from_userid)
        to_msgbox = MsgBox.MsgBox(to_userid)
        from_msgbox = MsgBox.MsgBox(from_userid)

        if (text_body == None):
            return 0

        if (not from_user.HasPerm(User.PERM_SEECLOAK) and to_userinfo.invisible and from_userid != to_userid and sender_mode != modes.CHAT1):
            return -2

        if (to_userinfo.mode == modes.LOCKSCREEN and sender_mode != modes.NEW):
            return -1

        if (not user.BeIgnored(to_userid) and sender_mode != modes.NEW):
            return -11

        if (to_userinfo.mode != modes.WEBEXPLORE and sender_mode != modes.NEW):
            if (to_msgbox.GetUnreadCount() > Config.MAXMESSAGE):
                return -12;

        to_msg = MsgHead.MsgHead()
        to_msg.time = int(time.time())
        to_msg.sent = 0
        to_msg.mode = sender_mode
        to_msg.id = from_userid
        to_msg.frompid = os.getpid()
        to_msg.topid = to_userinfo.pid

        from_msg = copy.copy(to_msg)
        from_msg.sent = 1
        from_msg.id = to_userid

        to_userinfo.load()
        if (to_userinfo.active == 0 or to_userinfo.pid == 0 or to_userinfo.userid != to_userid):
            return -14;

        try:
            os.kill(to_userinfo.pid, 0)
        except OSError:
            return -14

        if (to_msgbox.SaveMsgText(to_msg, text_body) < 0):
            return -21
        if (to_userid != from_userid and sender_mode != modes.NEW):
            if (from_msgbox.SaveMsgText(from_msg, text_body) < 0):
                return -21

        if (to_userinfo.mode == modes.WWW):
            to_userinfo.mailcheck |= UserInfo.CHECK_MSG
            to_userinfo.save()
            return 1

        if (to_userinfo.pid != 1):
            try:
                os.kill(to_userinfo.pid, signal.SIGUSR2)
            except OSError:
                return -13

        return 1

