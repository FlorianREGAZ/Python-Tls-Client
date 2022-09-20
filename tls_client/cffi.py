from sys import platform
from platform import machine
import ctypes
import os


if platform == 'darwin':
    file_ext = '-arm64.dylib' if machine() == "arm64" else '-x86.dylib'
elif platform in ('win32', 'cygwin'):
    file_ext = '.dll'
else:
    file_ext = '.so'

rootdir = os.path.abspath(os.path.dirname(__file__))
library = ctypes.cdll.LoadLibrary(f'{rootdir}/dependencies/tls-client{file_ext}')

# extract the exposed request function from the shared package
request = library.request
request.argtypes = [ctypes.c_char_p]
request.restype = ctypes.c_char_p