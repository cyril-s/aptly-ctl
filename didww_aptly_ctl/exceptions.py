class DidwwAptlyCtlError(Exception):
    def __init__(self, msg, original_exception=None, logger=None):
        if original_exception:
            self.msg = ": ".join([msg, str(original_exception)])
        else:
            self.msg = msg

        if logger:
            self.logger = logger

        if original_exception:
            self.original_exception = original_exception

