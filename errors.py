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
            svc.return_error(403, value.msg)
        elif (isinstance(value, WrongArgs)):
            svc.return_error(400, value.msg)
        elif (isinstance(value, NotFound)):
            svc.return_error(404, value.msg)
        elif (isinstance(value, ServerError)):
            svc.return_error(500, value.msg)
        else:
            svc.return_error(500, traceback.format_exc(value))
        return True
