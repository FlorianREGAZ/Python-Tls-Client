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

Example 1 - Custom:
```python
import tls_client

# You can find more details about the arguments in `session.py` e.g. what 1, 2, 3, 4 etc. represents in h2_settings
session = tls_client.Session(
    ja3_string="771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0",
    h2_settings={
      1: 65536,
      3: 1000,
      4: 6291456,
      6: 262144
    },
    h2_settings_order=[
        1,
        3,
        4,
        6
    ],
    pseudo_header_order=[
        ":method",
        ":authority",
        ":scheme",
        ":path"
    ],
    connection_flow=15663105
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

# Acknowledgements
Big shout out to [Bogdanfinn](https://github.com/bogdanfinn) for open sourcing his [tls-client](https://github.com/bogdanfinn/tls-client) in Golang.
Also to [requests](https://github.com/psf/requests), as most of the cookie handling is copied from it. :'D
<br/>
I wanted to keep the syntax as similar as possible to requests, as most people use it and are familiar with it!