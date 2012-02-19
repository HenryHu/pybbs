import time

class Log:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    _debug = True
    _info = True
    _warning = True
    _error = True

    @staticmethod
    def debug(msg):
        if (Log._debug):
            print "%s [DEBUG]" % time.ctime(), msg.encode('utf-8')
    
    @staticmethod
    def error(msg):
        if (Log._error):
            print Log.FAIL, "%s [ERROR] " % time.ctime(), msg.encode('utf-8'), Log.ENDC

    @staticmethod
    def warn(msg):
        if (Log._warning):
            print Log.WARNING, "%s [WARN] " % time.ctime(), msg.encode('utf-8'), Log.ENDC

    @staticmethod
    def info(msg):
        if (Log._info):
            print Log.OKGREEN, "%s [INFO] " % time.ctime(), msg.encode('utf-8'), Log.ENDC

