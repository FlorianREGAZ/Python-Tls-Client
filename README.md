# Python-TLS-Client
Python-TLS-Client is an advanced HTTP library based on requests and tls-client.

# Installation
```
pip install tls-client
```

# Examples
The syntax is inspired by [requests](https://github.com/psf/requests), so its very similar and there are only very few things that are different.

Example 1 - Preset:
```python
import tls_client

# `client_identifier` picks the browser profile to impersonate, e.g. chrome_120, firefox_120, safari_ios_17_0 or
# okhttp4_android_13. Every supported name is listed in tls_client/settings.py; unknown names raise a ValueError.

session = tls_client.Session(
    client_identifier="chrome_112",
    random_tls_extension_order=True
)

res = session.get(
    "https://www.example.com/",
    headers={
        "key1": "value1",
    },
    proxy="http://user:password@host:port"
)
```

Example 2 - Custom:
```python
import tls_client

session = tls_client.Session(
    # None switches from a preset to the settings below. Without it they are all ignored.
    client_identifier=None,
    ja3_string="771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0",
    h2_settings={
        "HEADER_TABLE_SIZE": 65536,
        "MAX_CONCURRENT_STREAMS": 1000,
        "INITIAL_WINDOW_SIZE": 6291456,
        "MAX_HEADER_LIST_SIZE": 262144
    },
    h2_settings_order=[
        "HEADER_TABLE_SIZE",
        "MAX_CONCURRENT_STREAMS",
        "INITIAL_WINDOW_SIZE",
        "MAX_HEADER_LIST_SIZE"
    ],
    supported_signature_algorithms=[
        "ECDSAWithP256AndSHA256",
        "PSSWithSHA256",
        "PKCS1WithSHA256",
        "ECDSAWithP384AndSHA384",
        "PSSWithSHA384",
        "PKCS1WithSHA384",
        "PSSWithSHA512",
        "PKCS1WithSHA512",
    ],
    supported_versions=["GREASE", "1.3", "1.2"],
    key_share_curves=["GREASE", "X25519"],
    cert_compression_algo="brotli",
    # The JA3 contains ALPN (16) and ALPS (17513), these fill them in.
    alpn_protocols=["h2", "http/1.1"],
    alps_protocols=["h2"],
    pseudo_header_order=[
        ":method",
        ":authority",
        ":scheme",
        ":path"
    ],
    connection_flow=15663105,
    header_order=[
        "accept",
        "user-agent",
        "accept-encoding",
        "accept-language"
    ]
)

res = session.post(
    "https://www.example.com/",
    headers={
        "key1": "value1",
    },
    json={
        "key1": "key2"
    }
)
```

Example 3 - Async:
```python
import asyncio
import tls_client

async def main():
    # Takes the same arguments as tls_client.Session.
    async with tls_client.AsyncSession(client_identifier="chrome_120") as session:
        responses = await asyncio.gather(
            *(session.get(f"https://www.example.com/{i}") for i in range(10))
        )
        print([res.status_code for res in responses])

asyncio.run(main())
```

# Pyinstaller / Pyarmor
**If you want to pack the library with Pyinstaller or Pyarmor, make sure to add this to your command:**

Linux with glibc (e.g. Ubuntu, Debian) / x86_64:
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-linux-ubuntu-amd64.so:tls_client/dependencies'
```

Linux / ARM64:
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-linux-arm64.so:tls_client/dependencies'
```

Linux with glibc / 32-bit x86:
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-linux-386.so:tls_client/dependencies'
```

Linux / 32-bit ARMv7 and later (e.g. 32-bit Raspberry Pi OS on a Raspberry Pi 2 or newer):
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-linux-armv7.so:tls_client/dependencies'
```

macOS on Intel x86 based Macs (pre-M1):
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-darwin-amd64.dylib:tls_client/dependencies'
```

macOS on Apple Silicon (M1 and later):
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-darwin-arm64.dylib:tls_client/dependencies'
```

Windows / 64-bit:
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-windows-64.dll;tls_client/dependencies'
```

Windows / 32-bit:
```
--add-binary '{path_to_library}/tls_client/dependencies/tls-client-windows-32.dll;tls_client/dependencies'
```

# Native library
The TLS and HTTP work is done by [bogdanfinn/tls-client](https://github.com/bogdanfinn/tls-client), a Go library that its author builds into shared libraries with [`cffi_dist/build.sh`](https://github.com/bogdanfinn/tls-client/blob/v1.16.0/cffi_dist/build.sh). This project compiles nothing: each wheel contains one unmodified asset from the upstream [v1.16.0 release](https://github.com/bogdanfinn/tls-client/releases/tag/v1.16.0), renamed as listed below.

| Library | Upstream release asset |
| --- | --- |
| `tls-client-darwin-amd64.dylib` | `tls-client-darwin-amd64-1.16.0.dylib` |
| `tls-client-darwin-arm64.dylib` | `tls-client-darwin-arm64-1.16.0.dylib` |
| `tls-client-linux-386.so` | `tls-client-xgo-1.16.0-linux-386.so` |
| `tls-client-linux-arm64.so` | `tls-client-linux-arm64-1.16.0.so` |
| `tls-client-linux-armv7.so` | `tls-client-linux-armv7-1.16.0.so` |
| `tls-client-linux-ubuntu-amd64.so` | `tls-client-linux-ubuntu-amd64-1.16.0.so` |
| `tls-client-windows-32.dll` | `tls-client-windows-32-1.16.0.dll` |
| `tls-client-windows-64.dll` | `tls-client-windows-64-1.16.0.dll` |

[`tls_client/dependencies/SHA256SUMS`](tls_client/dependencies/SHA256SUMS) lists the SHA-256 of every library, and each one matches the digest GitHub shows for the release asset. To check an installed library, run this in the installed `tls_client/dependencies` directory (on macOS, `shasum -a 256` instead of `sha256sum`):
```
sha256sum --check --ignore-missing SHA256SUMS
```

A source checkout has no library; download the one for your platform with `python scripts/fetch_library.py <library>`, which checks it against `SHA256SUMS`. To move to a new upstream release, change `VERSION` in `scripts/fetch_library.py` and run `python scripts/fetch_library.py --update-checksums`: it downloads every library, checks it against the digest GitHub lists for the asset, and rewrites `SHA256SUMS`. Upstream doesn't publish a checksum file of its own.

# Acknowledgements
Big shout out to [Bogdanfinn](https://github.com/bogdanfinn) for open sourcing his [tls-client](https://github.com/bogdanfinn/tls-client) in Golang.
Also I wanted to keep the syntax as similar as possible to [requests](https://github.com/psf/requests), as most people use it and are familiar with it!
