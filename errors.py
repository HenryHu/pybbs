import traceback

class NoPerm(Exception):
    pass

class WrongArgs(Exception):
    pass

class NotFound(Exception):
    pass

class ServerError(Exception):
    pass

class OutOfRange(Exception):
    pass

class Unauthorized(Exception):
    pass

class error_handler:
    def __init__(self, svc):
        self.svc = svc

    def __enter__(self):
        pass

    def __exit__(self, type, value, tb):
        if (value == None):
            return True
        if (isinstance(value, NoPerm)):
            self.svc.return_error(403, value.args[0])
        elif (isinstance(value, WrongArgs)):
            self.svc.return_error(400, value.args[0])
        elif (isinstance(value, Unauthorized)):
            self.svc.return_error(401, value.args[0])
        elif (isinstance(value, NotFound)):
            self.svc.return_error(404, value.args[0])
        elif (isinstance(value, OutOfRange)):
            self.svc.return_error(416, value.args[0])
        elif (isinstance(value, ServerError)):
            self.svc.return_error(500, value.args[0])
        else:
            self.svc.return_error(500, traceback.format_exc(value))
        return True
