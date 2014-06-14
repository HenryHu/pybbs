#!/usr/bin/env python
from Util import Util
import mailbox
import json
from errors import *

DEFAULT_MAIL_VIEW_COUNT = 20
MAIL_SIZE_UNLIMITED = -1

class Mail:
    @staticmethod
    def GET(svc, session, params, action):
        if (session is None): raise Unauthorized('login first')
        if not session.CheckScope('bbs'): raise NoPerm("out of scope")
        if (action == 'list'):
            folder = svc.get_str(params, 'folder', 'inbox')
            start = svc.get_int(params, 'start', 0)
            end = svc.get_int(params, 'end', 0)
            count = svc.get_int(params, 'count', 0)
            svc.writedata(Mail.List(session.GetUser(), folder, start, count, end))
        elif (action == 'view'):
            folder = svc.get_str(params, 'folder', 'inbox')
            index = svc.get_int(params, 'index')
            start = svc.get_int(params, 'start', 0)
            count = svc.get_int(params, 'count', 0)
            if start < 0 or count < 0:
                raise WrongArgs('start or count < 0')
            svc.writedata(Mail.View(session.GetUser(), folder, index, start, count))
        elif (action == 'check_unread'):
            folder = svc.get_str(params, 'folder', 'inbox')
            index = svc.get_int(params, 'index', 0)
            result = {'unread': Mail.CheckUnread(session.GetUser(), folder, index)}
            svc.writedata(json.dumps(result))
        elif action == 'quote':
            folder = svc.get_str(params, 'folder', 'inbox')
            mode = svc.get_str(params, 'mode', 'S')
            index = svc.get_int(params, 'index')
            (title, content) = session.GetUser().mbox.quote_mail(folder, mode,
                    index)
            result = {'title': title, 'content': content}
            svc.writedata(json.dumps(result))
        else:
            raise WrongArgs('unknown action')

    @staticmethod
    def POST(svc, session, params, action):
        if session is None: raise Unauthorized('login first')
        if not session.CheckScope('bbs'): raise NoPerm('out of scope')
        if action == 'send':
            title = svc.get_str(params, 'title')
            content = svc.get_str(params, 'content')
            receiver_id = svc.get_str(params, 'to')
            signature_id = svc.get_int(params, 'signature_id', 0)
            save_in_sent = svc.get_bool(params, 'save_in_sent', True)
            session.GetUser().SendMailTo(receiver_id, title, content,
                    signature_id, session, save_in_sent)
            result = {'result': 'ok'}
            svc.writedata(json.dumps(result))
        else:
            raise WrongArgs('unknown action')

    @staticmethod
    def List(user, folder, start, count, end):
        mbox = mailbox.MailBox(user.GetName())
        folder = mbox.get_folder(folder)
        total = folder.count()

        start, end = Util.CheckRange(start, end, count, DEFAULT_MAIL_VIEW_COUNT, total)
        if (start <= end and start >= 1 and end <= total):
            result = '{ "start": %d, "end": %d, "mails": [\n' % (start, end)
            first = True
            for i in range(start - 1, end):
                entry = folder.get_entry(i)
                if entry is None:
                    continue
                if not first:
                    result += ',\n'
                post = entry.GetInfo('mail')
                post['id'] = i+1
                result += json.dumps(post)
                first = False
            result += '\n]}'
            return result
        else:
            raise OutOfRange('out of range')

    @staticmethod
    def View(user, folder, index, start, count):
        mbox = mailbox.MailBox(user.GetName())
        folder = mbox.get_folder(folder)

        entry = folder.get_entry(index - 1)
        if (entry is None):
            raise OutOfRange('out of range')
        post = folder.get_content(index - 1)
        if (post is None):
            raise OutOfRange('out of range')

        info = dict(entry.GetInfo().items() + post.GetInfo(start, count).items())
        info['id'] = index

        if not entry.IsRead():
            entry.SetRead(True)
            folder.set_entry(index - 1, entry)
#            session.GetUserInfo().SetMailCheck()

        return json.dumps(info)

    @staticmethod
    def CheckUnread(user, folder = 'inbox', index = 0):
        mbox = mailbox.MailBox(user.GetName())
        folder = mbox.get_folder(folder)

        if (index == 0):
            index = folder.count()

        entry = folder.get_entry(index - 1)
        if (entry is None):
            raise OutOfRange('index out of range')
        return not entry.IsRead()

