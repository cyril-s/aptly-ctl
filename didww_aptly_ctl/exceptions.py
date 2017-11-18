
class DidwwAptlyCtlException(Exception):

    def __init__(self,  *args, **kwargs):
        # To allow printing exceptions from outer handling function to log it
        # using logger of function raising the exception so we can see from which module and
        # function exeption came
        if "logger" in kwargs:
            self.logger = kwargs.pop("logger")
        super(DidwwAptlyCtlException, self).__init__(*args, **kwargs)
