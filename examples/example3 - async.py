import asyncio
import tls_client

# You can also use the following as `client_identifier`:
# Chrome --> chrome_103, chrome_104, chrome_105, chrome_106, chrome_107, chrome_108, chrome109, Chrome110,
#            chrome111, chrome112
# Firefox --> firefox_102, firefox_104, firefox108, Firefox110
# Opera --> opera_89, opera_90
# Safari --> safari_15_3, safari_15_6_1, safari_16_0
# iOS --> safari_ios_15_5, safari_ios_15_6, safari_ios_16_0
# iPadOS --> safari_ios_15_6
# Android --> okhttp4_android_7, okhttp4_android_8, okhttp4_android_9, okhttp4_android_10, okhttp4_android_11,
#             okhttp4_android_12, okhttp4_android_13

session = tls_client.AsyncSession(
    client_identifier="chrome112",
    random_tls_extension_order=True
)


async def send_request():
    response = await session.post(
        "https://tls.peet.ws/api/tls",
        headers={
            "key1": "value1",
        },
        json={
            "key1": "key2"
        }
    )
    print(response.text)

loop = asyncio.get_event_loop()
loop.run_until_complete(send_request())

