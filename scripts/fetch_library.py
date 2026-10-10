"""Download native tls-client libraries from the upstream GitHub release into tls_client/dependencies.

Usage: python scripts/fetch_library.py tls-client-darwin-arm64.dylib [more filenames...]

Without arguments, lists the available filenames. If tls_client can't load its library because it is
missing, the error message names the file this machine needs. Every download is checked against
tls_client/dependencies/SHA256SUMS.

To move to a new upstream release, update VERSION (and the version in the README), then run:
python scripts/fetch_library.py --update-checksums
It downloads every library in ASSETS, checks each against the SHA-256 digest GitHub lists for the
release asset, and rewrites SHA256SUMS. Upstream publishes no checksum file of its own.
"""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

VERSION = "1.16.0"
DOWNLOAD_URL = "https://github.com/bogdanfinn/tls-client/releases/download/v{version}/{asset}"
RELEASE_API_URL = "https://api.github.com/repos/bogdanfinn/tls-client/releases/tags/v{version}"

# Local filename -> upstream release asset.
ASSETS = {
    "tls-client-darwin-amd64.dylib": "tls-client-darwin-amd64-{version}.dylib",
    "tls-client-darwin-arm64.dylib": "tls-client-darwin-arm64-{version}.dylib",
    "tls-client-linux-arm64.so": "tls-client-linux-arm64-{version}.so",
    "tls-client-linux-ubuntu-amd64.so": "tls-client-linux-ubuntu-amd64-{version}.so",
    "tls-client-windows-32.dll": "tls-client-windows-32-{version}.dll",
    "tls-client-windows-64.dll": "tls-client-windows-64-{version}.dll",
}

DEPENDENCIES_DIR = Path(__file__).resolve().parent.parent / "tls_client" / "dependencies"
# One "<sha256>  <filename>" line per library, as written by sha256sum.
CHECKSUMS = DEPENDENCIES_DIR / "SHA256SUMS"


def asset_name(filename: str) -> str:
    return ASSETS[filename].format(version=VERSION)


def download(filename: str) -> bytes:
    url = DOWNLOAD_URL.format(version=VERSION, asset=asset_name(filename))
    with urllib.request.urlopen(url) as response:
        return response.read()


def read_checksums() -> dict[str, str]:
    checksums = {}
    for line in CHECKSUMS.read_text().splitlines():
        digest, filename = line.split()
        checksums[filename] = digest
    return checksums


def fetch(filename: str, expected: str) -> None:
    data = download(filename)
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise SystemExit(f"Checksum mismatch for {asset_name(filename)}: expected {expected}, got {digest}")

    (DEPENDENCIES_DIR / filename).write_bytes(data)
    print(f"Downloaded {filename} ({len(data) / 1e6:.1f} MB) from tls-client v{VERSION}")


def update_checksums() -> None:
    with urllib.request.urlopen(RELEASE_API_URL.format(version=VERSION)) as response:
        release = json.load(response)
    # GitHub computes a digest ("sha256:<hex>") when an asset is uploaded; assets from before 2025 have none.
    published = {asset["name"]: asset.get("digest") for asset in release["assets"]}

    lines = []
    for filename in sorted(ASSETS):
        asset = asset_name(filename)
        if asset not in published:
            raise SystemExit(f"tls-client v{VERSION} has no release asset {asset}")
        digest = hashlib.sha256(download(filename)).hexdigest()
        if published[asset] is None:
            print(f"Warning: GitHub lists no digest for {asset}, pinning the downloaded file as is", file=sys.stderr)
        elif published[asset] != f"sha256:{digest}":
            raise SystemExit(f"Checksum mismatch for {asset}: GitHub lists {published[asset]}, got sha256:{digest}")
        lines.append(f"{digest}  {filename}\n")
        print(f"Checked {asset}")

    CHECKSUMS.write_text("".join(lines))
    print(f"Wrote {len(lines)} checksums for tls-client v{VERSION} to {CHECKSUMS}")


def main(args: list[str]) -> None:
    if args == ["--update-checksums"]:
        update_checksums()
        return

    unknown = [name for name in args if name not in ASSETS]
    if not args or unknown:
        if unknown:
            print(f"Unknown library: {', '.join(unknown)}", file=sys.stderr)
        print("Available libraries:", *ASSETS, sep="\n  ", file=sys.stderr)
        raise SystemExit(2)

    checksums = read_checksums()
    for filename in args:
        if filename not in checksums:
            raise SystemExit(f"{CHECKSUMS} has no checksum for {filename}; run with --update-checksums")
        fetch(filename, checksums[filename])


if __name__ == "__main__":
    main(sys.argv[1:])
