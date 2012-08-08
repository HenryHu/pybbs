#!/usr/bin/env python
import json
from Util import Util
import Config
import base64
from errors import *

class Store:
    @staticmethod
    def GET(svc, session, params, action):
        raise WrongArgs('unknown action')

    @staticmethod
    def POST(svc, session, params, action):
        if (session == None): raise Unauthorized('login first')

        if (action == "new"):
            item = svc.get_str(params, 'item')
            content = svc.get_str(params, 'content')
            store_id = Store.new(item, content)
            result = {}
            result['id'] = store_id
            svc.writedata(json.dumps(result))
        else:
            raise WrongArgs('unknown action')

    @staticmethod
    def new(item, content):
        if (item != 'attachment'):
            raise WrongArgs("unknown item type")
        try:
            data = base64.b64decode(content)
        except:
            raise WrongArgs("base64 decoding failure")
        filename = Util.RandomStr(16)
        filepath = Store.path_from_id(filename)
        fp = None
        try_count = 16 # good luck!
        while (try_count > 0):
            while (try_count > 0):
                try:
                    fp = open(filepath, "rb")
                    # ... success?
                    filename = Util.RandomStr(16)
                    filepath = Store.path_from_id(filename)

                except:
                    break

                try_count -= 1

            # at least we can't open it...
            try:
                with open(filepath, "wb") as fp:
                    fp.write(data)

                return filename
            except:
                # ... failed...
                filename = Util.RandomStr(16)
                filepath = Store.path_from_id(filename)

            try_count -= 1

        raise ServerError("can't store content")

    @staticmethod
    def path_from_id(id):
        return Config.BBS_ROOT + "/tmp/" + id + ".tmp"

    @staticmethod
    def verify_id(id):
        if (not Util.CheckStr(id)):
            return False
        if (len(id) != 16):
            return False
        try:
            filepath = Store.path_from_id(id)
            with open(filepath, "rb"):
                pass
        except:
            return False

        return True
