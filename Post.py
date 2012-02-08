#!/usr/bin/env python

from Util import Util
import struct
import Config
import string
import os
import time

GENERATE_POST_SUFIX = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
GENERATE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

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
                    bo.GetAttachment(svc, session, params, id)
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
                if (Post.IsPictureAttach(name)):
                    picturelist.append((Util.gbkDec(name), offset))
                else:
                    attachlist.append((Util.gbkDec(name), offset))

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
            name = Util.ReadString(fp)

            # read the size
            s = fp.read(4)
            size = struct.unpack('!I', s)[0]   # big endian

            # read the content
            content = fp.read(size)
        finally:
            fp.close()
        return (name, content)

    @staticmethod
    def GeneratePostFile(path, use_subdir):
        filename = None
        now = int(time.time())
        xlen = len(GENERATE_POST_SUFIX)
        for i in range(0, 10):
            if (use_subdir):
                rn = int(xlen * random.random())
                filename = "%c/M.%lu.%c%c" % GENERATE_ALPHABET[rn], now, GENERATE_POST_SUFIX[(pid + i) % 62], GENERATE_POST_SUFIX[(pid * i) % 62]
            else:
                filename = "M.%lu.%c%c" % now, GENERATE_POST_SUFIX[(pid + i) % 62], GENERATE_POST_SUFIX[(pid * i) % 62]
            fname = "%s/%s" % path, filename
            fp = os.open(fname, O_CREAT | O_EXCL | O_WRONLY, 0644)
            if (fp != None):
                fp.close()
                return filename
        return None

from BoardManager import BoardManager
