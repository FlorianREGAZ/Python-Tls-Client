import ctypes
import functools
import os
import platform
import sys
import sysconfig

from .exceptions import UnsupportedPlatformError

# Platforms with a prebuilt upstream library, as named in the wheels.
SUPPORTED_PLATFORMS = (
    "macOS on x86_64 or arm64",
    "Linux with glibc on x86_64 or aarch64",
    "Windows on x86 or x86_64",
)

DEPENDENCIES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "dependencies")


def _is_musl() -> bool:
    if not sys.platform.startswith("linux"):
        return False
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
    elif sys.platform.startswith("linux") and is_64bit and not _is_musl():
        # A 32-bit userland on a 64-bit kernel still reports the kernel's machine, hence the is_64bit check.
        if machine in ("x86_64", "amd64"):
            target = "linux-ubuntu-amd64.so"
        elif machine in ("aarch64", "arm64"):
            target = "linux-arm64.so"

    if target is None:
        musl = _is_musl()
        bits = "64" if is_64bit else "32"
        # Upstream does publish a musl build, but musl refuses to dlopen it (Go c-shared uses initial-exec TLS).
        reason = " musl-based systems such as Alpine can't load the native library." if musl else ""
        raise UnsupportedPlatformError(
            f"tls_client has no native library for {sys.platform}{' (musl)' if musl else ''} on {platform.machine()} "
            f"({bits}-bit Python).{reason} Supported platforms: {'; '.join(SUPPORTED_PLATFORMS)}."
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
    library = ctypes.cdll.LoadLibrary(path)
    for function in (library.request, library.freeMemory, library.destroySession):
        function.argtypes = [ctypes.c_char_p]
        function.restype = ctypes.c_char_p
    # freeMemory returns nothing; reading its return register as a string pointer could crash.
    library.freeMemory.restype = None
    return library


@functools.cache
def load_library() -> ctypes.CDLL:
    """The native library, loaded on first use.

    Loading it starts the Go runtime, which doesn't survive fork(): a forked child that calls into a runtime
    started by its parent deadlocks. Loading lazily keeps `import tls_client` safe before forking.
    """
    return _load_library()


def request(payload: bytes) -> bytes:
    response: bytes = load_library().request(payload)
    return response


def freeMemory(response_id: bytes) -> None:
    load_library().freeMemory(response_id)


def destroySession(payload: bytes) -> bytes:
    response: bytes = load_library().destroySession(payload)
    return response
