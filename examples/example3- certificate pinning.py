import tls_client

session = tls_client.Session(
    certificate_pinning={
        "example.com": [
            "NQvyabcS99nBqk/nZCUF44hFhshrkvxqYtfrZq3i+Ww=",
            "4a6cdefI7OG6cuDZka5NDZ7FR8a60d3auda+sKfg4Ng=",
            "x4QzuiC810K5/cMjb05Qm4k3Bw5zBn4lTdO/nEW/Td4="
        ]
    }
)

res = session.get(
    "https://www.example.com/",
    headers={
        "key1": "value1",
    },
    proxy="http://user:password@host:port"
)