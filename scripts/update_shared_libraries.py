import requests

shared_library_version = "1.7.2"
github_download_url = "https://github.com//bogdanfinn/tls-client/releases/download/v{}/{}"
github_repo_filenames = [
    # Windows
    f"tls-client-windows-32-v{shared_library_version}.dll",
    f"tls-client-windows-64-v{shared_library_version}.dll",
    # MacOS
    f"tls-client-darwin-arm64-v{shared_library_version}.dylib",
    f"tls-client-darwin-amd64-v{shared_library_version}.dylib",
    # Linux
    f"tls-client-linux-alpine-amd64-v{shared_library_version}.so",
    f"tls-client-linux-ubuntu-amd64-v{shared_library_version}.so",
    f"tls-client-linux-arm64-v{shared_library_version}.so"
]
dependency_filenames = [
    # Windows
    "tls-client-32.dll",
    "tls-client-64.dll",
    # MacOS
    "tls-client-arm64.dylib",
    "tls-client-x86.dylib",
    # Linux
    "tls-client-amd64.so",
    "tls-client-x86.so",
    "tls-client-arm64.so"
]

for github_filename, dependency_filename in zip(github_repo_filenames, dependency_filenames):
    response = requests.get(
        url=github_download_url.format(shared_library_version, github_filename)
    )

    with open(f"../tls_client/dependencies/{dependency_filename}", "wb") as f:
        f.write(response.content)
