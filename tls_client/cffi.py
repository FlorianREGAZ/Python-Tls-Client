import ctypes
import os
import platform
import sys
import sysconfig

from .exceptions import UnsupportedPlatformError

# Platforms with a prebuilt upstream library, as named in the wheels.
SUPPORTED_PLATFORMS = (
    "macOS on x86_64 or arm64",
    "Linux with glibc on x86_64 or aarch64",
    "Linux with musl (e.g. Alpine) on x86_64",
    "Windows on x86 or x86_64",
)

DEPENDENCIES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "dependencies")


def _is_musl() -> bool:
    # Only glibc defines this name; on musl os.confstr raises ValueError.
    try:
        return not os.confstr("CS_GNU_LIBC_VERSION")
    except (AttributeError, OSError, ValueError):
        return True


def library_filename() -> str:
    """Name of the upstream library this interpreter can load, e.g. ``tls-client-linux-ubuntu-amd64.so``.

    The choice follows the interpreter, not the OS: a 32-bit Python on 64-bit Windows needs the 32-bit DLL.
    """
    machine = platform.machine().lower()
    is_64bit = sys.maxsize > 2**32
    target = None

    if sys.platform == "darwin":
        # Under Rosetta, machine() reports x86_64, which is what an x86_64 interpreter needs.
        target = {"arm64": "darwin-arm64.dylib", "x86_64": "darwin-amd64.dylib"}.get(machine)
    elif sys.platform == "win32":
        # machine() reports the OS architecture on Windows; sysconfig reports the interpreter's.
        target = {"win-amd64": "windows-64.dll", "win32": "windows-32.dll"}.get(sysconfig.get_platform())
    elif sys.platform == "cygwin":
        if machine in ("x86_64", "i686", "i386"):
            target = "windows-64.dll" if is_64bit else "windows-32.dll"
    elif sys.platform.startswith("linux") and is_64bit:
        # A 32-bit userland on a 64-bit kernel still reports the kernel's machine, hence the is_64bit check.
        if machine in ("x86_64", "amd64"):
            target = "linux-alpine-amd64.so" if _is_musl() else "linux-ubuntu-amd64.so"
        elif machine in ("aarch64", "arm64") and not _is_musl():
            target = "linux-arm64.so"

    if target is None:
        libc = " (musl)" if sys.platform.startswith("linux") and _is_musl() else ""
        bits = "64" if is_64bit else "32"
        raise UnsupportedPlatformError(
            f"tls_client has no native library for {sys.platform}{libc} on {platform.machine()} "
            f"({bits}-bit Python). Supported platforms: {'; '.join(SUPPORTED_PLATFORMS)}."
        )
    return f"tls-client-{target}"


def _load_library() -> ctypes.CDLL:
    filename = library_filename()
    path = os.path.join(DEPENDENCIES_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"The native library {filename} is missing from {DEPENDENCIES_DIR}. "
            "Wheels on PyPI include it, so this usually means tls_client runs from a source checkout. "
            f"Download it with: python scripts/fetch_library.py {filename}"
        )
    return ctypes.cdll.LoadLibrary(path)


library = _load_library()

# extract the exposed request function from the shared package
request = library.request
request.argtypes = [ctypes.c_char_p]
request.restype = ctypes.c_char_p

freeMemory = library.freeMemory
freeMemory.argtypes = [ctypes.c_char_p]
freeMemory.restype = ctypes.c_char_p

destroySession = library.destroySession
destroySession.argtypes = [ctypes.c_char_p]
destroySession.restype = ctypes.c_char_p
