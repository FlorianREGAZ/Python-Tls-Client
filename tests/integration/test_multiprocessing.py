import multiprocessing
import subprocess
import sys

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="needs the fork start method"),
]

# The parent imports tls_client but makes no request, then a forked child does. The Go runtime doesn't
# survive fork(), so this hung while the library was loaded at import time.
PARENT = """
import multiprocessing
import sys

import tls_client


def child(url):
    with tls_client.Session() as session:
        sys.exit(0 if session.get(url, timeout_seconds=10).status_code == 200 else 1)


if __name__ == "__main__":
    process = multiprocessing.get_context("fork").Process(target=child, args=(sys.argv[1],))
    process.start()
    process.join(30)
    if process.is_alive():
        process.kill()
        sys.exit("the forked child hung")
    sys.exit(process.exitcode)
"""


def test_forked_child_can_make_requests_after_parent_imported_tls_client(httpbin):
    # A fresh interpreter, because this one has loaded the library already.
    result = subprocess.run([sys.executable, "-c", PARENT, f"{httpbin.url}/get"], capture_output=True, timeout=60)

    assert result.returncode == 0, result.stderr.decode()
