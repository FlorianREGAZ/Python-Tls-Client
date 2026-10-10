import tls_client

session = tls_client.Session(client_identifier="chrome_152")

# Redirects are only followed with allow_redirects=True.
res = session.get("https://httpbin.org/cookies/set?flavour=chocolate", allow_redirects=True)
print(res.url)  # https://httpbin.org/cookies
print([r.status_code for r in res.history])  # [302]

# Cookies set on any hop are kept in the session and sent with later requests.
print(session.cookies.get_dict())  # {'flavour': 'chocolate'}

# Cookies removed from the session are no longer sent.
session.cookies.clear()
print(session.get("https://httpbin.org/cookies").json())  # {'cookies': {}}
