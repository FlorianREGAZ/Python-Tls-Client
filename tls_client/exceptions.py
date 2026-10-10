class TLSClientException(IOError):
    """General error with the TLS client"""


class UnsupportedPlatformError(TLSClientException):
    """No native library is available for this OS, CPU architecture or C library"""
