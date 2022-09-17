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