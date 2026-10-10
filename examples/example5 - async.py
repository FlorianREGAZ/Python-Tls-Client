import asyncio

import tls_client


async def main() -> None:
    # Takes the same arguments as tls_client.Session.
    async with tls_client.AsyncSession(client_identifier="chrome_152") as session:
        responses = await asyncio.gather(*(session.get(f"https://httpbin.org/get?page={i}") for i in range(10)))
        print([res.status_code for res in responses])


asyncio.run(main())
