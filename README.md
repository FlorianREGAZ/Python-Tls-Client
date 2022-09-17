# Python-TLS-Client
Python-TLS-Client is an advanced HTTP library based on requests and tls-client.

# Installation
```
pip install tls-client
```

# Examples
The syntax is insprired from [requests](https://github.com/psf/requests), so its very similar and their are only very few things that are different.

Example 1 - Preset:
```python
import tls_client

# You can also use the following as `client_identifier`:
# Chrome --> chrome_103, chrome_104, chrome_105
# Firefox --> firefox_102, firefox_104
# Opera --> opera_89, opera_90
# Safari --> safari_15_3, safari_15_6_1, safari_16_0
# iOS --> safari_ios_15_5, safari_ios_15_6, safari_ios_16_0
# iPadOS --> safari_ios_15_6

session = tls_client.Session(
    client_identifier="chrome_105"
)

res = session.get(
    "https://www.example.com/",
    headers={
        "key1": "value1",
    },
    proxy="http://user:password@host:port"
)
```

# Acknowledgements
Big shout out to [Bogdanfinn](https://github.com/bogdanfinn) for open sourcing his [tls-client](https://github.com/bogdanfinn/tls-client) in Golang.
Also to [requests](https://github.com/psf/requests), as most of the cookie handling is copied from it. :'D
<br/>
I wanted to keep the syntax as similar as possible to requests, as most people use it and are familiar with it!
