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

# Acknowledgements
Big shout out to [Bogdanfinn](https://github.com/bogdanfinn) for open sourcing his [tls-client](https://github.com/bogdanfinn/tls-client) in Golang.
Also I wanted to keep the syntax as similar as possible to [requests](https://github.com/psf/requests), as most people use it and are familiar with it!
