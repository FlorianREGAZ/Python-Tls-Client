import tls_client

# `client_identifier` picks the browser profile to impersonate, e.g. chrome_120, firefox_120, safari_ios_17_0 or
# okhttp4_android_13. Every supported name is listed in tls_client/settings.py; unknown names raise a ValueError.

session = tls_client.Session(client_identifier="chrome_112", random_tls_extension_order=True)

res = session.get(
    "https://www.example.com/",
    headers={
        "key1": "value1",
    },
    proxy="http://user:password@host:port",
)
