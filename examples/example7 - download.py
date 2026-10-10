import tls_client

session = tls_client.Session(client_identifier="chrome_152")

# .content is the exact bytes the server sent. timeout is in seconds and can be a float.
res = session.get("https://httpbin.org/image/png", timeout=10)
with open("image.png", "wb") as f:
    f.write(res.content)

# .text is decoded with the charset from the Content-Type header or the page itself.
# Set .encoding when a page declares the wrong one.
res = session.get("https://httpbin.org/html", timeout=2.5)
res.encoding = "iso-8859-1"
print(res.text[:100])
