#!/usr/bin/env python
import Config
import Board
import Post
import os

class MailBox:
    name = ''

    def __init__(self, username):
        self.name = username

    def path_of(self, path):
        return "%s/mail/%c/%s/%s" % (Config.BBS_ROOT, self.name[0].upper(), self.name, path)

    def folder_path(self, folder):
        if (folder == 'inbox'):
            return self.path_of(".DIR")
        elif (folder == 'sent'):
            return self.path_of(".SENT")
        else:
            # fail-safe
            return self.path_of(".DIR")

    def get_folder(self, folder):
        return Folder(self, folder, self.folder_path(folder))

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

        return st.st_size / Board.PostEntry.size

    def get_entry(self, index):
        if (index < 0 or index >= self.count()):
            return None

        try:
            with open(self.path, "rb") as dirf:
                dirf.seek(index * Board.PostEntry.size)
                data = dirf.read(Board.PostEntry.size)
                if (len(data) < Board.PostEntry.size):
                    return None
                return Board.PostEntry(data)
        except:
            return None

    def get_content(self, index):
        entry = self.get_entry(index)
        if (entry is None):
            return None
        path = self.mailbox.path_of(entry.filename)
        post = Post.Post(path)
        return post

