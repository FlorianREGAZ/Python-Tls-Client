import tls_client

session = tls_client.Session(client_identifier="chrome_152")

with open("report.pdf", "rb") as f:
    res = session.post(
        "https://www.example.com/upload",
        data={"title": "Report"},
        files={"file": f, "notes": ("notes.txt", "some text", "text/plain")},
    )
