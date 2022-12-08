from sys import platform
from platform import machine
import ctypes
import os


if platform == 'darwin':
    file_ext = '-arm64.dylib' if machine() == "arm64" else '-x86.dylib'
elif platform in ('win32', 'cygwin'):
    file_ext = '.dll'
elif platform == "linux" and machine() == 'armv7l':
    file_ext = '-arm32.so'
else:
    file_ext = '-x86.so' if "x86" in machine() else '-amd64.so'

root_dir = os.path.abspath(os.path.dirname(__file__))
library = ctypes.cdll.LoadLibrary(f'{root_dir}/dependencies/tls-client{file_ext}')

# extract the exposed request function from the shared package
request = library.request
request.argtypes = [ctypes.c_char_p]
request.restype = ctypes.c_char_p