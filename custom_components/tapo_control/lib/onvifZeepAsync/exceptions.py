""" Core exceptions raised by the ONVIF Client """

# Error codes setting
# Error unknown, e.g, HTTP errors
ERR_ONVIF_UNKNOWN = 1
# Protocol error returned by WebService,
# e.g:DataEncodingUnknown, MissingAttr, InvalidArgs, ...
ERR_ONVIF_PROTOCOL = 2
# Error about WSDL instance
ERR_ONVIF_WSDL = 3
# Error about Build
ERR_ONVIF_BUILD = 4


class ONVIFError(Exception):
    """ONVIF Exception class."""

    def __init__(self, err):
        self.reason = "Unknown error: " + str(err)
        self.code = ERR_ONVIF_UNKNOWN
        super().__init__(err)

    def __str__(self):
        return self.reason


class ONVIFTimeoutError(ONVIFError):
    """ONVIF Timeout Exception class."""

    def __init__(self, err):
        super().__init__(err)


class ONVIFAuthError(ONVIFError):
    """ONVIF Authentication Exception class."""

    def __init__(self, err):
        super().__init__(err)
