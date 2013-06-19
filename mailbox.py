#!/usr/bin/env python
import Config
import PostEntry
import Post
import os
import shutil
from Util import Util
from errors import *

MAIL_SIZE_UNLIMITED = 9999

class MailBox:
    name = ''

    def __init__(self, username):
        self.name = username

    def path_of(self, path):
        if path:
            return "%s/mail/%c/%s/%s" % (Config.BBS_ROOT, self.name[0].upper(), self.name, path)
        else:
            return "%s/mail/%c/%s" % (Config.BBS_ROOT, self.name[0].upper(), self.name)

    def folder_path(self, folder):
        if (folder == 'inbox'):
            return self.path_of(".DIR")
        elif (folder == 'sent'):
            return self.path_of(".SENT")
        elif folder == 'deleted':
            return self.path_of('.DELETED')
        else:
            # fail-safe
            return self.path_of(".DIR")

    def get_folder(self, folder):
        return Folder(self, folder, self.folder_path(folder))

    def create(self):
        path = self.path_of("")
        if os.path.isdir(path):
            return True
        if os.path.exists(path):
            return False
        try:
            os.makedirs(path, 0755)
            return True
        except:
            return False

    def new_entry(self, owner, title, content):
        if not self.create():
            raise ServerError("fail to create mail dir for user '%s'" % self.name)
        entry = PostEntry.PostEntry()
        entry.owner = owner
        entry.title = Util.gbkEnc(title)
        # create file
        entry.filename = Post.Post.GetPostFilename(self.path_of(""), False)
        encoded_content = Util.gbkEnc(content)
        entry.eff_size = len(encoded_content)
        path = self.path_of(entry.filename)

        with open(path, "wb") as f:
            f.write(encoded_content)
        return entry

    def new_mail(self, sender, title, content):
        mentry = self.new_entry(sender.name, title, content)

        folder = self.get_folder('inbox')
        folder.add_entry(mentry)
        return mentry.eff_size

    def new_sent_mail(self, receiver, title, content):
        msent = self.new_entry(receiver.name, title, content)
        msent.SetRead(True)

        folder = self.get_folder('sent')
        folder.add_entry(msent)
        return msent.eff_size

    def quote_mail(self, folder_name, mode, index):
        folder = self.get_folder(folder_name)
        if folder is None:
            raise NotFound("no such mailbox: %s" % folder_name)
        entry = folder.get_entry(index - 1)
        path = self.path_of(entry.filename)

        quote_content = Util.gbkDec(Post.Post.DoQuote(mode, path, False))
        if entry.title[:3] == "Re:":
            quote_title = Util.gbkDec(entry.title)
        else:
            quote_title = "Re: " + Util.gbkDec(entry.title)
        return (quote_title, quote_content)

    def full(self):
        if Config.MAIL_SIZE_LIMIT != MAIL_SIZE_UNLIMITED:
            num = (self.get_folder('inbox').get_mail_num() +
                    self.get_folder('sent').get_mail_num() +
                    self.get_folder('deleted').get_mail_num())
            # TODO: custom mail folder
            if num > Config.MAIL_NUM_LIMIT:
                return True
        return False

class Folder:
    def __init__(self, mailbox, name, path):
        self.name = name
        self.path = path
        self.mailbox = mailbox

    def count(self):
        try:
            st = os.stat(self.path)
        except:
            return 0

        return st.st_size / PostEntry.PostEntry.size

    def add_entry(self, entry):
        return (Util.AppendRecord(self.path, entry.pack()) == 0)

    def get_entry(self, index):
        if (index < 0 or index >= self.count()):
            return None

        try:
            with open(self.path, "rb") as dirf:
                dirf.seek(index * PostEntry.PostEntry.size)
                data = dirf.read(PostEntry.PostEntry.size)
                if (len(data) < PostEntry.PostEntry.size):
                    return None
                return PostEntry.PostEntry(data)
        except:
            return None

    def set_entry(self, index, entry):
        if (index < 0 or index >= self.count()):
            return False

        try:
            with open(self.path, "r+b") as dirf:
                dirf.seek(index * PostEntry.PostEntry.size)
                dirf.write(entry.pack())
                return True
        except:
            return False

    def get_content(self, index):
        entry = self.get_entry(index)
        if (entry is None):
            return None
        path = self.mailbox.path_of(entry.filename)
        post = Post.Post(path, entry, True)
        return post

    def get_mail_num(self):
        return os.stat(self.path).st_size / PostEntry.PostEntry.size
