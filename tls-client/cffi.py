import ctypes

# TODO: load the tls-client shared package for your OS
library = ctypes.cdll.LoadLibrary('./dependencies/tls-client-windows-64-0.5.2.dll')

# extract the exposed request function from the shared package
request = library.request
request.argtypes = [ctypes.c_char_p]
request.restype = ctypes.c_char_p