"""Turns the wheel into a platform wheel for the one native library in tls_client/dependencies.

The libraries are not in git, so hatchling would leave them out; this hook adds the library back
and tags the wheel for its platform. Fetch the library first with scripts/fetch_library.py.
"""

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Library filename -> wheel platform tag. The floors come from the upstream binaries: the Linux
# builds need glibc 2.4 (amd64) and 2.17 (arm64), and the macOS builds target macOS 13. There is no
# musl wheel: musl can't dlopen the upstream musl build.
PLATFORM_TAGS = {
    "tls-client-darwin-amd64.dylib": "macosx_13_0_x86_64",
    "tls-client-darwin-arm64.dylib": "macosx_13_0_arm64",
    "tls-client-linux-arm64.so": "manylinux_2_17_aarch64",
    "tls-client-linux-ubuntu-amd64.so": "manylinux_2_17_x86_64",
    "tls-client-windows-32.dll": "win32",
    "tls-client-windows-64.dll": "win_amd64",
}


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        # Editable installs load the library straight from the source tree.
        if self.target_name != "wheel" or version == "editable":
            return

        dependencies = Path(self.root) / "tls_client" / "dependencies"
        libraries = sorted(p.name for p in dependencies.iterdir() if p.suffix in (".so", ".dylib", ".dll"))
        if len(libraries) != 1 or libraries[0] not in PLATFORM_TAGS:
            raise RuntimeError(
                f"A wheel needs exactly one known native library in {dependencies}, found {libraries or 'none'}. "
                "Download one with: python scripts/fetch_library.py <filename>"
            )

        library = libraries[0]
        # The library is loaded with ctypes, so one wheel serves every Python 3 version.
        build_data["pure_python"] = False
        build_data["tag"] = f"py3-none-{PLATFORM_TAGS[library]}"
        build_data["force_include"][str(dependencies / library)] = f"tls_client/dependencies/{library}"
