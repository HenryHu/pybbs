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
            print "[DEBUG]", msg
    
    @staticmethod
    def error(msg):
        if (Log._error):
            print Log.FAIL, "[ERROR] ", msg, Log.ENDC

    @staticmethod
    def warn(msg):
        if (Log._warning):
            print Log.WARNING, "[WARN] ", msg, Log.ENDC

    @staticmethod
    def info(msg):
        if (Log._info):
            print Log.OKGREEN, "[INFO] ", msg, Log.ENDC

