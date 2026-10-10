# Python-TLS-Client
Python-TLS-Client is an advanced HTTP library based on requests and tls-client.

# Installation
```
pip install tls-client
```

# Examples
The syntax is inspired by [requests](https://github.com/psf/requests), so its very similar and there are only very few things that are different.

Example - Preset:
```python
import tls_client

# `client_identifier` picks the browser profile to impersonate, e.g. chrome_152, firefox_148, safari_ios_26_0 or
# okhttp4_android_13. Every supported name is listed in tls_client/settings.py; unknown names raise a ValueError.

session = tls_client.Session(
    client_identifier="chrome_152",
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

More examples:
- [Custom TLS fingerprint](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example2%20-%20custom.py)
- [Certificate pinning](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example3-%20certificate%20pinning.py)
- [File upload](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example4%20-%20file%20upload.py)
- [Async](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example5%20-%20async.py)
- [Redirects and cookies](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example6%20-%20redirects%20and%20cookies.py)
- [Downloads and encodings](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example7%20-%20download.py)
- [Multiprocessing](https://github.com/FlorianREGAZ/Python-Tls-Client/blob/main/examples/example8%20-%20multiprocessing.py)

# Acknowledgements
Big shout out to [Bogdanfinn](https://github.com/bogdanfinn) for open sourcing his [tls-client](https://github.com/bogdanfinn/tls-client) in Golang.
Also I wanted to keep the syntax as similar as possible to [requests](https://github.com/psf/requests), as most people use it and are familiar with it!
