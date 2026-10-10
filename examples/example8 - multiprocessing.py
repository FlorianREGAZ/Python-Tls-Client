import multiprocessing

import tls_client


def fetch(url: str) -> int:
    session = tls_client.Session(client_identifier="chrome_152")
    return session.get(url).status_code


if __name__ == "__main__":
    session = tls_client.Session(client_identifier="chrome_152")
    print(session.get("https://www.example.com/").status_code)

    # The parent has made a request, so the native library is loaded and a fork()ed child would hang.
    # Use "spawn" or "forkserver" instead.
    with multiprocessing.get_context("spawn").Pool(4) as pool:
        print(pool.map(fetch, ["https://www.example.com/"] * 8))
