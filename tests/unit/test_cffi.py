import pytest

from tls_client import cffi
from tls_client.exceptions import TLSClientException, UnsupportedPlatformError


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch):
    """Pretends to run on another platform: host(sys_platform, machine, ...)."""

    def pretend(
        sys_platform: str,
        machine: str,
        *,
        is_64bit: bool = True,
        musl: bool = False,
        sysconfig_platform: str = "",
    ) -> None:
        monkeypatch.setattr(cffi.sys, "platform", sys_platform)
        monkeypatch.setattr(cffi.sys, "maxsize", 2**63 - 1 if is_64bit else 2**31 - 1)
        monkeypatch.setattr(cffi.platform, "machine", lambda: machine)
        monkeypatch.setattr(cffi.sysconfig, "get_platform", lambda: sysconfig_platform)
        monkeypatch.setattr(cffi, "_is_musl", lambda: musl)

    return pretend


@pytest.mark.parametrize(
    ("sys_platform", "machine", "options", "expected"),
    [
        ("darwin", "arm64", {}, "tls-client-darwin-arm64.dylib"),
        ("darwin", "x86_64", {}, "tls-client-darwin-amd64.dylib"),
        ("linux", "x86_64", {}, "tls-client-linux-ubuntu-amd64.so"),
        ("linux", "aarch64", {}, "tls-client-linux-arm64.so"),
        ("win32", "AMD64", {"sysconfig_platform": "win-amd64"}, "tls-client-windows-64.dll"),
        # 32-bit Python on 64-bit Windows: the interpreter decides, not the OS.
        ("win32", "AMD64", {"sysconfig_platform": "win32", "is_64bit": False}, "tls-client-windows-32.dll"),
        ("cygwin", "x86_64", {}, "tls-client-windows-64.dll"),
    ],
)
def test_picks_the_library_for_the_interpreter(host, sys_platform, machine, options, expected):
    host(sys_platform, machine, **options)

    assert cffi.library_filename() == expected


@pytest.mark.parametrize(
    ("sys_platform", "machine", "options"),
    [
        # These used to fall through to the x86_64 Alpine library.
        ("linux", "armv7l", {"is_64bit": False}),
        ("linux", "i686", {"is_64bit": False}),
        ("linux", "riscv64", {}),
        # 32-bit userland on a 64-bit kernel.
        ("linux", "x86_64", {"is_64bit": False}),
        # musl can't dlopen the upstream libraries.
        ("linux", "x86_64", {"musl": True}),
        ("linux", "aarch64", {"musl": True}),
        # This used to load the x86_64 DLL, which an arm64 interpreter can't.
        ("win32", "ARM64", {"sysconfig_platform": "win-arm64"}),
        ("freebsd14", "amd64", {}),
    ],
)
def test_unsupported_platforms_raise_a_clear_error(host, sys_platform, machine, options):
    host(sys_platform, machine, **options)

    with pytest.raises(UnsupportedPlatformError, match=f"no native library for {sys_platform}.* on {machine}"):
        cffi.library_filename()


def test_unsupported_platform_error_lists_the_supported_platforms(host):
    host("linux", "aarch64", musl=True)

    with pytest.raises(UnsupportedPlatformError) as excinfo:
        cffi.library_filename()

    message = str(excinfo.value)
    assert "linux (musl) on aarch64 (64-bit Python)" in message
    assert "musl-based systems such as Alpine can't load the native library" in message
    assert all(supported in message for supported in cffi.SUPPORTED_PLATFORMS)
    assert isinstance(excinfo.value, TLSClientException)


def test_missing_library_says_how_to_download_it(monkeypatch, tmp_path):
    monkeypatch.setattr(cffi, "DEPENDENCIES_DIR", str(tmp_path))

    with pytest.raises(FileNotFoundError, match=r"python scripts/fetch_library\.py tls-client-"):
        cffi._load_library()
