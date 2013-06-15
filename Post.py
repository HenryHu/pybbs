#!/usr/bin/env python
# vim: set fileencoding=utf-8

from Util import Util
import struct
import Config
import string
import os
import binascii
import re
import time
import json
import random
from errors import *
from Log import Log
import curses.ascii

ATTACHMENT_PAD = '\0\0\0\0\0\0\0\0'
ATTACHMENT_SIZE = 0
QUOTELEV = 1

class Post:
    def __init__(self, path, entry, is_mail = False):
        self.path = path
        self.textlen = 0
        self.file = None
        self.is_mail = is_mail
        self.entry = entry

    def GetContent(self):
        content = Post.ReadPostText(self.path)
        self.textlen = content[1]
        return content[0]

    def GetBody(self):
        content = self.GetContent()
        return content[content.find('\n\n')+2:]

    def GetAttachListByType(self):
        return Post.GetAttachmentListByType(self.path, self.textlen)

    def GetAttachList(self):
        return Post.GetAttachmentList(self.path, self.textlen)

    def GetInfo(self):
        info = {}
        info['content'] = self.GetContent()
        attachlist = self.GetAttachListByType()
        info['picattach'] = attachlist[0]
        info['otherattach'] = attachlist[1]
        return info

    @staticmethod
    def GetReplyFile(svc, params, board):
        re_id = svc.get_int(params, "re_id", 0)
        re_xid = svc.get_int(params, "re_xid", 0)
        re_mode = svc.get_str(params, "re_mode", 'normal')
        if (re_id != 0 and re_xid == 0):
            raise WrongArgs("re_xid must be given with re_id")

        if (re_id != 0):
            (re_file, _) = board.FindPost(re_id, re_xid, re_mode)
        else:
            re_file = None

        return re_file

    @staticmethod
    def GET(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')
        if not session.CheckScope('bbs'): raise NoPerm("out of scope")
        bo = BoardManager.GetBoardByParam(svc, params)
        if (bo == None): raise NotFound('board not found')

        if (not bo.CheckPostPerm(session.GetUser())):
            raise WrongArgs('permission denied')

        if (action == 'search'):
            raise WrongArgs('not implemented')
        elif action == 'prepare':
            for_action = svc.get_str(params, 'for')
            if for_action == 'new':
                anony = bool(svc.get_int(params, "anonymous", 0))
                refile = Post.GetReplyFile(svc, params, bo)
                user = session.GetUser()
                try:
                    attach = json.loads(svc.get_str(params, 'attachments'))
                except:
                    attach = None
                
                detail = bo.PreparePostArticle(user, refile, anony, attach)
                result = {"error": detail, "signature_id" : user.GetSigID()}
                svc.writedata(json.dumps(result))
            else:
                raise WrongArgs("unknown action to prepare")
        else:
            _id = svc.get_int(params, 'id')
            if (action == 'view'):
                bo.GetPost(svc, session, params, _id)
            elif action == 'nextid':
                bo.GetNextPostReq(svc, session, params, _id)
            elif action == 'get_attach':
                bo.GetAttachmentReq(svc, session, params, _id)
            elif action == 'quote':
                xid = svc.get_int(params, 'xid')
                index_mode = svc.get_str(params, 'index_mode', 'normal')
                include_mode = svc.get_str(params, 'mode', 'S')
                bo.QuotePost(svc, _id, xid, include_mode, index_mode)
            else:
                raise WrongArgs("unknown action")

    @staticmethod
    def POST(svc, session, params, action):
        if (session == None): raise Unauthorized("login first")
        if not session.CheckScope('bbs'): raise NoPerm("out of scope")
        bo = BoardManager.GetBoardByParam(svc, params)
        if (bo == None): raise NotFound("no such board")

        if (action == "new"):
            title = svc.get_str(params, "title").decode('utf-8')
            content = svc.get_str(params, "content").decode('utf-8')
            signature_id = svc.get_int(params, "signature_id", 0)
            anony = bool(svc.get_int(params, "anonymous", 0))
            mailback = bool(svc.get_int(params, "mailback", 0))
            re_file = Post.GetReplyFile(svc, params, bo)
            try:
                attach = json.loads(svc.get_str(params, 'attachments'))
            except:
                attach = None

            bo.PostArticle(session.GetUser(), title,
                    content, re_file, signature_id, anony, mailback, session, attach)
            svc.writedata('{"result": "ok"}')
        elif action == "delete":
            post_id = svc.get_int(params, "id", 0)
            post_xid = svc.get_int(params, "xid")
            mode = svc.get_str(params, "mode", "normal")
            bo.DelPost(session.GetUser(), post_id, post_xid, mode)
            svc.writedata('{"result": "ok"}')
        elif action == "edit":
            post_id = svc.get_int(params, "id", 0)
            post_xid = svc.get_int(params, "xid")
            mode = svc.get_str(params, "mode", "normal")
            try:
                title = svc.get_str(params, "title").decode('utf-8')
            except:
                title = None
            try:
                content = svc.get_str(params, "content").decode('utf-8')
            except:
                content = None
            try:
                add_attach = json.loads(svc.get_str(params, 'new_attachments'))
            except:
                add_attach = []
            try:
                del_attach = json.loads(svc.get_str(params, 'del_attachments'))
            except:
                del_attach = set()
            bo.EditPost(session, post_xid, post_id, title, content, mode,
                    del_attach, add_attach)
            svc.writedata('{"result": "ok"}')
        else:
            raise WrongArgs("unknown action")

    @staticmethod
    def GetAttachmentListByType(path, base = 0):
        attachlist = Post.GetAttachmentList(path, base)
        picturelist = []
        otherlist = []
        for entry in attachlist:
            if Post.IsPictureAttach(entry['name']):
                picturelist.append(entry)
            else:
                otherlist.append(entry)
        return (picturelist, otherlist)

    @staticmethod
    def GetAttachmentList(path, base = 0):
        try:
            fp = open(path, 'rb')
        except IOError:
            raise ServerError('fail to load post')
        attachlist = []
        try:
            start = base
            offset = Post.SeekAttachment(fp, start)
            while (start != offset):
                # read the name
                name = Util.ReadString(fp)
                attach = {'name': Util.gbkDec(name), 'offset': offset}
                attachlist.append(attach)

                # read the size
                s = fp.read(4)
                size = struct.unpack('!I', s)[0]   # big endian
                start = fp.tell() + size

                #seek to next attachment
                offset = Post.SeekAttachment(fp, start)

        finally:
            fp.close()
        return attachlist

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

                lastline = u'\n\033[m\033[1;%2dm※ 来源:·%s %s·[FROM: %s]\033[m\n' % (color, Config.Config.GetString("BBS_FULL_NAME", "Python BBS"), Config.Config.GetString("NAME_BBS_ENGLISH", "PyBBS"), from_str)
                fp.write(lastline.encode('gbk'))

        except IOError:
            Log.error("Post.AddLogInfo: IOError on %s" % filepath)
            pass

    @staticmethod
    def WriteHeader(fp, user, in_mail, board, title, anony, mode, session):
        uid = user.name[:20].decode('gbk')
        uname = user.userec.username[:40].decode('gbk')
        bname = board.name.decode('gbk')
        bbs_name = Config.Config.GetString('BBS_FULL_NAME', 'Python BBS')

        if (in_mail):
            fp.write((u'寄信人: %s (%s)\n', uid, uname).encode('gbk'))
        else:
            if (anony):
                pid = (binascii.crc32(session.GetID()) % 0xffffffff) % (200000 - 1000) + 1000
                fp.write((u'发信人: %s (%s%d), 信区: %s\n' % (bname, Config.Config.GetString('NAME_ANONYMOUS', 'Anonymous'), pid, bname)).encode('gbk'))
            else:
                fp.write((u'发信人: %s (%s), 信区: %s\n' % (uid, uname, bname)).encode('gbk'))

        fp.write((u'标  题: %s\n' % (title)).encode('gbk'))

        if (in_mail):
            fp.write((u'发信站: %s (%24.24s)\n' % (bbs_name, time.ctime())).encode('gbk'))
            fp.write((u'来  源: %s \n' % session._fromip).encode('gbk'))
        elif (mode != 2):
            fp.write((u'发信站: %s (%24.24s), 站内\n' % (bbs_name, time.ctime())).encode('gbk'))
        else:
            fp.write((u'发信站: %s (%24.24s), 转信\n' % (bbs_name, time.ctime())).encode('gbk'))

        fp.write('\n')

    @staticmethod
    def AddSig(fp, user, sig):
        user.SetSigID(sig)
        if (sig == 0):
            return

        if (sig < 0):
            signum = user.GetSignatureCount()
            if (signum == 0):
                sig = 0
            else:
                sig = random.randint(1, signum)

        sig_fname = user.MyFile("signatures")
        valid_ln = 0
        tmpsig = []
        # hack: c code limit the size of buf
        # we must follow this, or the line number would be different
        # fgets(256) = readline(255)
        buf_size = 255
        try:
            with open(sig_fname, "r") as sigfile:
                fp.write('\n--\n')
                for i in xrange(0, (sig - 1) * Config.MAXSIGLINES):
                    line = sigfile.readline(buf_size)
                    if (line == ""):
                        return
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

        for i in range(0, valid_ln):
            fp.write(tmpsig[i])

    @staticmethod
    def DoQuote(include_mode, quote_file, for_post):
        if (quote_file == ""):
            return "";
        if (include_mode == 'N'):
            return "\n";
        quser = ""
        result = ""
        with open(quote_file, "rb") as inf:
            buf = Post.SkipAttachFgets(inf)
            match_user = re.match('[^:]*: *(.*\))[^)]*$', buf)
            if (match_user):
                quser = match_user.group(1)
            if (include_mode != 'R'):
                if (for_post):
                    result = result + (u"\n【 在 %s 的大作中提到: 】\n".encode('gbk') % quser)
                else:
                    result = result + (u"\n【 在 %s 的来信中提到: 】\n".encode('gbk') % quser)
            if (include_mode == 'A'):
                while (True):
                    buf = Post.SkipAttachFgets(inf)
                    if (buf == ""): break
                    result += ": %s" % buf
            else:
                # skip header
                while (True):
                    buf = Post.SkipAttachFgets(inf)
                    if (buf == "" or buf[0] == '\n'): break
                if (include_mode == 'R'):
                    while (True):
                        buf = Post.SkipAttachFgets(inf)
                        if (buf == ""): break
                        if (not Post.IsOriginLine(buf)):
                            result += buf
                else:
                    line_count = 0
                    while (True):
                        buf = Post.SkipAttachFgets(inf)
                        if (buf == "" or buf == "--\n"): break
                        if (len(buf) > 250):
                            buf = buf[250] + "\n"
                        if (not Post.IsGarbageLine(buf)):
                            result += ": %s" % buf
                            if (include_mode == 'S'):
                                line_count += 1
                                if (line_count >= Config.QUOTED_LINES):
                                    result += ": ..................."
                                    break
        result += "\n"
        return result

    @staticmethod
    def SkipAttachFgets(f):
        ret = ""
        matchpos = 0
        while (True):
            ch = f.read(1)
            if (ch == ""): break
            if (ch == ATTACHMENT_PAD[matchpos]):
                matchpos += 1
                if (matchpos == ATTACHMENT_SIZE):
                    ch = f.read(1)
                    while (ch != '\0'):
                        ch = f.read(1)
                    d = f.read(4)
                    size = struct.unpack('!I', d)[0]
                    f.seek(size, 1)
                    ret = ret[:-ATTACHMENT_SIZE]
                    matchpos = 0

                    continue
            ret += ch
            if (ch == '\n'):
                break
        return ret

    def GetOriginLine(self):
        for line in self.GetBody().split('\n'):
            if Post.IsOriginLine(Util.gbkEnc(line)):
                return line
        return ""

    @staticmethod
    def IsOriginLine(str):
        tmp = (u"※ 来源:·%s " % Config.Config.GetString("BBS_FULL_NAME", "Python BBS")).encode('gbk')
        return tmp in str

    @staticmethod
    def IsGarbageLine(line):
        qlevel = 0
        while (line != "" and (line[0] == ':' or line[0] == '>')):
            line = line[1:]
            if (line != "" and line[0] == ' '):
                line = line[1:]
                qlevel += 1
                if (qlevel - 1 >= QUOTELEV):
                    return True
        while (line != "" and (line[0] == ' ' or line[0] == '\t')):
            line = line[1:]

        if (qlevel >= QUOTELEV):
            if (u"提到:\n".encode('gbk') in line
                or u": 】\n".encode('gbk') in line
                or line[:3] == "==>"
                or u"的文章 说".encode('gbk') in line):
                return True
        return line != "" and line[0] == '\n'

    @staticmethod
    def ReadPostText(path):
        try:
            postf = open(path, 'rb')
        except IOError:
            raise ServerError("fail to load post")
        try:
            ret = ''
            while (True):
                data = postf.read(512)
                i = data.find('\0')
                if (i != -1):
                    ret = ret + data[:i]
                    break
                else:
                    ret = ret + data
                    if (len(data) < 512):
                        break
        finally:
            postf.close()
        return (Util.gbkDec(ret), len(ret))

    @staticmethod
    def GetAttachLink(session, board, postentry):
        return "http://%s/bbscon.php?b=%s&f=%s" % (session.GetMirror(Config.Config.GetInt('ATTACHMENT_PORT', 80)), board.name, postentry.filename)

    @staticmethod
    def GetSanAttachName(attach_name):
        attach_name_gbk = Util.gbkEnc(attach_name)
        san_attach_name = ''
        for ch in attach_name_gbk:
            if (ch != '/' and ch != '\\' and
                ch != '*' and ch != '?' and
                ch != '$' and ch != '~' and
                (ch.isalnum() or curses.ascii.ispunct(ch) or ord(ch) >= 0x80)):
                san_attach_name += ch
            else:
                san_attach_name += '_'
        return san_attach_name

    @staticmethod
    def AddAttachFrom(postf, attach_name, attachf, length):
        postf.write(ATTACHMENT_PAD)
        pos = postf.tell()
        postf.write(Post.GetSanAttachName(attach_name))
        postf.write('\0')
        postf.write(struct.pack('!I', length))
        left = length
        while left > 0:
            buf = attachf.read(4096 if left >= 4096 else left)
            postf.write(buf)
            left -= len(buf)
        return pos

    def AddAttachSelf(self, attach_name, attach_file):
        try:
            attach_stat = os.stat(attach_file)
            if (attach_stat.st_size > Config.MAX_ATTACHSIZE):
                raise WrongArgs("attachment too large: %d > %d" %
                        (attach_stat.st_size, Config.MAX_ATTACHSIZE))
            with open(attach_file, "rb") as attachf:
                return Post.AddAttachFrom(self.file, attach_name, attachf,
                        attach_stat.st_size)
        finally:
            try:
                os.unlink(attach_file)
            except:
                pass

    @staticmethod
    def AddAttach(postfile_name, attach_name, attach_file):
        try:
            try:
                attach_stat = os.stat(attach_file)
                if (attach_stat.st_size > Config.MAX_ATTACHSIZE):
                    return 0
                with open(attach_file, "rb") as attachf:
                    with open(postfile_name, "ab") as postf:
                        Post.AddAttachFrom(postf, attach_name, attachf,
                                attach_stat.st_size)

                return attach_stat.st_size
            except Exception as e:
                Log.warn("fail to add attach: %r" % e)
                return 0
        finally:
            try:
                os.unlink(attach_file)
            except:
                pass

    def EditHeaderFrom(self, other, new_title):
        with open(other.path, "rb") as otherf:
            while True:
                buf = Post.SkipAttachFgets(otherf)
                if buf == "" or buf == "\n":
                    break
                # buf: encoded in gbk
                if new_title is not None and buf[:8] == u"标  题: ".encode('gbk'):
                    self.file.write(Util.gbkEnc(u"标  题: %s\n" % new_title))
                else:
                    self.file.write(buf)
        self.file.write("\n")

    def EditContent(self, content, session, orig_post):
        src_hit = False
        if not Config.ADD_EDITMARK:
            mark_added = True
        else:
            mark_added = False
        user = session.GetUser()
        anony = self.entry.is_anony()
        time_str = time.ctime()[4:]
        if not anony:
            from_str = session._fromip
            if self.is_mail:
                # aqua 2008.6.16: display year of modification
                mod_mark = u"\033[36m※ 修改:·%s 于 %20.20s 修改本信·[FROM: %s]\033[m\n" % (user.name, time_str, from_str)
            else:
                mod_mark = u"\033[36m※ 修改:·%s 于 %20.20s 修改本文·[FROM: %s]\033[m\n" % (user.name, time_str, from_str)
        else:
            from_str = Config.Config.GetString("NAME_ANONYMOUS_FROM", "Anonymous")
            if self.is_mail:
                mod_mark = u"\033[36m※ 修改:·%s 于 %20.20s 修改本信·[FROM: %s]\033[m\n" % (self.entry.owner, time_str, from_str)
            else:
                mod_mark = u"\033[36m※ 修改:·%s 于 %20.20s 修改本文·[FROM: %s]\033[m\n" % (self.entry.owner, time_str, from_str)
        orig_mark = Util.gbkEnc(orig_post.GetOriginLine())
        mod_mark = Util.gbkEnc(mod_mark)

        for line in content.split('\n'):
            if line[:11] == u"\033[36m※ 修改:·":
                continue
            if Post.IsOriginLine(line.encode('gbk')):
                src_hit = True
                if not mark_added:
                    self.file.write(mod_mark)
                    mark_added = True
                self.file.write(orig_mark)
            else:
                self.file.write(Util.gbkEnc(line))
            self.file.write("\n")

        if not mark_added:
            self.file.write(mod_mark)
        if not src_hit:
            self.file.write(orig_mark)

    def AppendAttachFrom(self, other, attach_entry):
        with open(other.path, "rb") as fp:
            fp.seek(attach_entry['offset'] - 8)

            # check for attachment mark
            if (fp.read(8) != '\0\0\0\0\0\0\0\0'):
                raise IOError

            # read the name
            name = Util.ReadString(fp)

            # read the size
            s = fp.read(4)
            size = struct.unpack('!I', s)[0]   # big endian

            return Post.AddAttachFrom(self.file, attach_entry['name'], fp, size)

    def open(self, mode = ""):
        if not mode:
            if os.path.isfile(self.path):
                mode = 'r+b'
            else:
                mode = 'wb'
        self.file = open(self.path, mode)

    def close(self):
        if self.file:
            self.file.close()

    def pos(self):
        return self.file.tell()

from BoardManager import BoardManager
