#!/usr/bin/env python
# vim: set fileencoding=utf-8

from Util import Util
import struct
import Config
import string
import os
import binascii
import time

class Post:

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None): return
        bo = BoardManager.GetBoardByParam(svc, params)
        if (bo == None): return

        if (not bo.CheckPostPerm(session.GetUser())):
            svc.send_response(403, 'Permission denied')
            svc.end_headers()
            return

        if (action == 'search'):
            return
        else:
            if (params.has_key('id')):
                id = int(params['id'])
                if (action == 'view'):
                    bo.GetPost(svc, session, params, id)
                elif action == 'nextid':
                    bo.GetNextPostReq(svc, session, params, id)
                elif action == 'get_attach':
                    bo.GetAttachmentReq(svc, session, params, id)
                else:
                    svc.send_response(400, 'Unknown action')
                    svc.end_headers()
            else:
                svc.send_response(400, 'Lack of post id')
                svc.end_headers()
                return

    @staticmethod
    def POST(svc, session, params, action):
        if (session == None): return
        bo = BoardManager.GetBoardName(svc, params)
        if (bo == None): return
        # TODO
        svc.return_error(400, 'Unknown action')
        return

    @staticmethod
    def GetAttachmentList(fp):
        picturelist = []
        attachlist = []
        try:
            start = 0
            offset = Post.SeekAttachment(fp, start)
            while (start != offset):
                # read the name
                name = Util.ReadString(fp)
                attach = {'name': Util.gbkDec(name), 'offset:': offset}
                if (Post.IsPictureAttach(name)):
                    picturelist.append(attach)
                else:
                    attachlist.append(attach)

                # read the size
                s = fp.read(4)
                size = struct.unpack('!I', s)[0]   # big endian
                start = fp.tell() + size

                #seek to next attachment
                offset = Post.SeekAttachment(fp, start)

        finally:
            fp.close()
        return (picturelist, attachlist)

    @staticmethod
    def IsPictureAttach(name):
        ext = string.lower(os.path.splitext(name)[1])  # get the ext
        return (ext in ['.bmp', '.gif', '.jpg', '.jpeg', '.png'])
    
    @staticmethod
    def SeekAttachment(fp, start):
        fp.seek(start)
        offset = start
        zcount = 0;
        while (zcount < 8):
            c = fp.read(1)
            if (c == ''):
                break
            offset = offset + 1
            if (c == '\0'):
                zcount = zcount + 1
            else:
                zcount = 0
        if (zcount == 8):
            return offset
        else:
            return start

    @staticmethod
    def ReadAttachment(filename, offset):
        fp = open(filename, "rb")
        try:
            fp.seek(offset-8)
    
            # check if is an atachment
            if (fp.read(8) != '\0\0\0\0\0\0\0\0'):
                raise IOError

            # read the name
            name = Util.ReadString(fp).decode('gbk')

            # read the size
            s = fp.read(4)
            size = struct.unpack('!I', s)[0]   # big endian

            # read the content
            content = fp.read(size)
        finally:
            fp.close()
        return (name, content)

    @staticmethod
    def AddLogInfo(filepath, user, session, anony, has_sig):
        color = (user.userec.numlogins % 7) + 31
        if (anony):
            from_str = Config.Config.GetString("NAME_ANONYMOUS_FROM", "Anonymous")
        else:
            from_str = session._fromip

        try:
            with open(filepath, "ab") as fp:
                if (has_sig):
                    fp.write('\n')
                else:
                    fp.write('\n--\n')

                lastline = '\n\033[m\033[1;%2dm※ 来源:·%s %s·[FROM: %s]\033[m\n' % (color, Config.Config.GetString("BBS_FULL_NAME", "Python BBS"), Config.Config.GetString("NAME_BBS_ENGLISH", "PyBBS"), from_str)
                fp.write(lastline.encode('gbk'))

        except IOError:
            pass

    @staticmethod
    def WriteHeader(file, user, in_mail, board, title, anony, mode, session):
        uid = user.name[:20].decode('gbk')
        uname = user.userec.username[:40].decode('gbk')
        bname = board.name.decode('gbk')
        bbs_name = Config.Config.GetString('BBS_FULL_NAME', 'Python BBS')

        if (in_mail):
            fp.write((u'寄信人: %s (%s)\n', uid, uname).encode('gbk'))
        else:
            if (anony):
                fake_pid = (binascii.crc32(session.GetID()) % 0xffffffff) % (200000 - 1000) + 1000
                fp.write((u'发信人: %s (%s%d), 信区: %s\n' % (bname, Config.Config.GetString('NAME_ANONYMOUS', 'Anonymous'), pid, bname)).encode('gbk'))
            else:
                fp.write((u'发信人: %s (%s), 信区: %s\n' % (uid, uname, bname)).encode('gbk'))

        fp.write((u'标  题: %s\n' % (title)).encode('gbk'))

        if (in_mail):
            fp.write((u'发信站: %s (%24.24s)\n', bbs_name, time.ctime()).encode('gbk'))
            fp.write((u'来  源: %s \n', session._fromip).encode('gbk'))
        elif (mode != 2):
            fp.write((u'发信站: %s (%24.24s), 站内\n', bbs_name, time.ctime()).encode('gbk'))
        else:
            fp.write((u'发信站: %s (%24.24s), 转信\n', bbs_name, time.ctime()).encode('gbk'))

        fp.write('\n')

    @staticmethod
    def AddSig(fp, user, sig):
        if (sig == 0):
            return
        sig_fname = user.OwnFile("signatures")
        valid_ln = 0
        tmpsig = []
        try:
            with open(sig_fname, "r") as sigfile:
                fp.write('\n--\n')
                for i in xrange(0, (sig - 1) * Config.MAXSIGLINES):
                    line = sigfile.readline()
                    if (line == ""):
                        return
                for i in range(0, Config.MAXSIGLINES):
                    line = sigfile.readline()
                    if (line != ""):
                        if (line[0] != '\n'):
                            valid_ln = i + 1
                        tmpsig += [line]
                    else:
                        break
        except IOError:
            Log.error("Post.AddSig: IOError on %s" % sig_fname)

        for i in range(0, valid_ln):
            fp.write(tmpsig[i])
            fp.write('\n')

from BoardManager import BoardManager
