from sys import platform
import ctypes
import os

rootdir = os.path.abspath(os.path.dirname(__file__))
dll_ext = 'dylib' if platform == 'darwin' else 'dll' if platform in ('win32', 'cygwin') else 'so'
library = ctypes.cdll.LoadLibrary(f'{rootdir}/dependencies/tls-client.{dll_ext}')

# extract the exposed request function from the shared package
request = library.request
request.argtypes = [ctypes.c_char_p]
request.restype = ctypes.c_char_p