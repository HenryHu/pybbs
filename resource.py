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
            svc.writedata(open(os.path.join(Config.Config.GetString("BBS_DATASVC_ROOT", ""), "res", action)).read())
        elif Resource.indir_re.match(action):
            match = Resource.indir_re.match(action)
            svc.writedata(open(os.path.join(Config.Config.GetString("BBS_DATASVC_ROOT", ""), "res", match.group(1), match.group(2))).read())
        else:
            raise NoPerm("no permission")


