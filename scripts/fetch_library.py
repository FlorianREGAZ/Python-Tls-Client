"""Download native tls-client libraries from the upstream GitHub release into tls_client/dependencies.

Usage: python scripts/fetch_library.py tls-client-darwin-arm64.dylib [more filenames...]

Without arguments, lists the available filenames. If tls_client fails to import because its library is
missing, the error message names the file this machine needs.

To move to a new upstream release, update VERSION and every hash in SHA256. GitHub lists the digests on
the release page, or run: gh release view v<VERSION> -R bogdanfinn/tls-client --json assets
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

VERSION = "1.16.0"
DOWNLOAD_URL = "https://github.com/bogdanfinn/tls-client/releases/download/v{version}/{asset}"

# Local filename -> SHA-256 of the upstream asset for VERSION.
SHA256 = {
    "tls-client-darwin-amd64.dylib": "6463457ea713a96b3b8c94fd9d8746e7bc510cb6784fcf0f4bb64d9c83e3251a",
    "tls-client-darwin-arm64.dylib": "99984d013921c753ab29d28720cb099eff6adf63538347e13652cb5cfe5bdc02",
    "tls-client-linux-alpine-amd64.so": "83c8702e8e8af2e5629277f422e77384a8780ac63c7f20988269a82d78e835ae",
    "tls-client-linux-arm64.so": "e398622f99c0ce8fccb50ff6e414f373b5932a0277ece90468a796992f0ae518",
    "tls-client-linux-ubuntu-amd64.so": "2ec853496634545e7a7ea028715763948d55bbdd97aca7ecaa9fea8c2ebb08df",
    "tls-client-windows-32.dll": "5203a36f80ea3f9cdfa43bf072a775702d1802acb8e4304e78905210f67dd2af",
    "tls-client-windows-64.dll": "53dca636b32d965ee6fe4562f39df959b2063febaa3d740efa925d1873cf11d7",
}

DEPENDENCIES_DIR = Path(__file__).resolve().parent.parent / "tls_client" / "dependencies"


def asset_name(filename: str) -> str:
    """tls-client-darwin-arm64.dylib -> tls-client-darwin-arm64-1.16.0.dylib"""
    stem, ext = filename.rsplit(".", 1)
    return f"{stem}-{VERSION}.{ext}"


def fetch(filename: str) -> None:
    url = DOWNLOAD_URL.format(version=VERSION, asset=asset_name(filename))
    with urllib.request.urlopen(url) as response:
        data = response.read()

    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256[filename]:
        raise SystemExit(f"Checksum mismatch for {url}: expected {SHA256[filename]}, got {digest}")

    (DEPENDENCIES_DIR / filename).write_bytes(data)
    print(f"Downloaded {filename} ({len(data) / 1e6:.1f} MB) from tls-client v{VERSION}")


def main(filenames: list[str]) -> None:
    unknown = [name for name in filenames if name not in SHA256]
    if not filenames or unknown:
        if unknown:
            print(f"Unknown library: {', '.join(unknown)}", file=sys.stderr)
        print("Available libraries:", *SHA256, sep="\n  ", file=sys.stderr)
        raise SystemExit(2)

    for filename in filenames:
        fetch(filename)


if __name__ == "__main__":
    main(sys.argv[1:])
