import time
import sys
import traceback

class Log:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    DEBUG = '\033[90m'

    _debug = True
    _info = True
    _warning = True
    _error = True

    @staticmethod
    def debug(msg):
        if (Log._debug):
            print Log.DEBUG, "%s [DEBUG]" % time.ctime(), msg.encode('utf-8'), Log.ENDC
            sys.stdout.flush()
    
    @staticmethod
    def error(msg):
        if (Log._error):
            print Log.FAIL, "%s [ERROR]" % time.ctime(), msg.encode('utf-8'), Log.ENDC
            exc_info = sys.exc_info()
            if exc_info[0] is not None:
                # handling exception
                traceback.print_exc()
            sys.stdout.flush()

    @staticmethod
    def warn(msg):
        if (Log._warning):
            print Log.WARNING, "%s [WARN] " % time.ctime(), msg.encode('utf-8'), Log.ENDC
            sys.stdout.flush()

    @staticmethod
    def info(msg):
        if (Log._info):
            print Log.OKGREEN, "%s [INFO] " % time.ctime(), msg.encode('utf-8'), Log.ENDC
            sys.stdout.flush()

