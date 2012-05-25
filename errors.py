import traceback

class NoPerm(Exception):
    pass

class WrongArgs(Exception):
    pass

class NotFound(Exception):
    pass

class ServerError(Exception):
    pass

class error_handler:
    def __init__(self, svc):
        self.svc = svc

    def __enter__(self):
        pass

    def __exit__(self, type, value, tb):
        if (isinstance(value, NoPerm)):
            self.svc.return_error(403, value.msg)
        elif (isinstance(value, WrongArgs)):
            self.svc.return_error(400, value.msg)
        elif (isinstance(value, NotFound)):
            self.svc.return_error(404, value.msg)
        elif (isinstance(value, ServerError)):
            self.svc.return_error(500, value.msg)
        else:
            self.svc.return_error(500, traceback.format_exc(value))
        return True
