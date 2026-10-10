class TLSClientException(IOError):
    """General error with the TLS client"""


class TooManyRedirects(TLSClientException):
    """A request with allow_redirects was redirected more than 30 times"""


class UnsupportedPlatformError(TLSClientException):
    """No native library is available for this OS, CPU architecture or C library"""
