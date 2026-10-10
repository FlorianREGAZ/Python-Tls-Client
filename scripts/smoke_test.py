"""Check an installed tls_client wheel: it ships exactly one library, loads it, and can make a request.

Run with the interpreter the wheel is installed in, in isolated mode so the source tree can't shadow it:
python -I scripts/smoke_test.py tls-client-linux-ubuntu-amd64.so
"""

import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main(expected_library: str) -> None:
    import tls_client
    from tls_client import cffi
    from tls_client.__version__ import __version__

    shipped = sorted(p.name for p in Path(cffi.DEPENDENCIES_DIR).iterdir() if p.suffix in (".so", ".dylib", ".dll"))
    assert shipped == [expected_library], f"wheel ships {shipped}, expected [{expected_library}]"
    assert cffi.library_filename() == expected_library, f"detected {cffi.library_filename()}"

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tls_client.Session() as session:
        response = session.get(f"http://127.0.0.1:{server.server_port}/")
    server.shutdown()

    assert response.status_code == 200, response.status_code
    assert response.text == "ok", response.text
    print(f"tls_client {__version__} works with {expected_library} from {cffi.DEPENDENCIES_DIR}")


if __name__ == "__main__":
    main(sys.argv[1])
