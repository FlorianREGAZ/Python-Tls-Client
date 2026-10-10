import tls_client

# You can also use the following as `client_identifier`:
# Chrome --> chrome_103, chrome_104, chrome_105, chrome_106, chrome_107, chrome_108, chrome109, Chrome110,
#            chrome111, chrome112, chrome_116_PSK, chrome_116_PSK_PQ, chrome_117, chrome_120
# Firefox --> firefox_102, firefox_104, firefox108, Firefox110, firefox_117, firefox_120
# Opera --> opera_89, opera_90
# Safari --> safari_15_3, safari_15_6_1, safari_16_0
# iOS --> safari_ios_15_5, safari_ios_15_6, safari_ios_16_0
# iPadOS --> safari_ios_15_6
# Android --> okhttp4_android_7, okhttp4_android_8, okhttp4_android_9, okhttp4_android_10, okhttp4_android_11,
#             okhttp4_android_12, okhttp4_android_13
#
# more client identifiers can be found in settings.py

session = tls_client.Session(
    client_identifier="chrome_112",
    random_tls_extension_order=True
)

res = session.get(
    "https://www.example.com/",
    headers={
        "key1": "value1",
    },
    proxy="http://user:password@host:port"
)