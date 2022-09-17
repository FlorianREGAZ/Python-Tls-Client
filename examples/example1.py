import tls_client

session = tls_client.Session(
    client_identifier="chrome_105"
)

res = session.get(
    "https://www.google.com/"
)
print(res)

