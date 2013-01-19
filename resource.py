import re
import Config
import os
from errors import *

class Resource:
    basic_re = re.compile('^[a-z-_]+\.[a-z]+$')
    indir_re = re.compile('^([a-z]+)/([a-z-_]+\.[a-z]+)$')
    @staticmethod
    def GET(svc, session, params, action):
        if Resource.basic_re.match(action):
            path = os.path.join(Config.Config.GetString("BBS_DATASVC_ROOT", ""), "res", action)
        elif Resource.indir_re.match(action):
            match = Resource.indir_re.match(action)
            path = os.path.join(Config.Config.GetString("BBS_DATASVC_ROOT", ""), "res", match.group(1), match.group(2))
        else:
            raise NoPerm("no permission")

        if not os.path.isfile(path):
            raise NoPerm("no permission")

        path = os.path.realpath(path)
        if not path.startswith(os.path.join(Config.Config.GetString("BBS_DATASVC_ROOT", ""), "res")):
            raise NoPerm("no permission")

        svc.writedata(open(path).read())

    @staticmethod
    def POST(svc, session, params, action):
        return Resource.GET(svc, session, params, action)


