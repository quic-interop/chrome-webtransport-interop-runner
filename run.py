"""Shared test logic for WebTransport interop runner (Chrome and Firefox)."""

import os
import sys
from collections import defaultdict
from urllib.parse import urlparse

DOWNLOADS = "/downloads/"
WWW = "/www/"

testcases = {
    "handshake": "runHandshake",
    "transfer": "runTransfer",
    "transfer-unidirectional-receive": "runTransferUnidirectional",
    "transfer-bidirectional-receive": "runTransferBidirectional",
    "transfer-datagram-receive": "runTransferDatagram",
}


def parse_client_requests(s: str) -> dict[str, list[str]]:
    """Parse REQUESTS env (space-separated URLs) into host+first_segment -> list of path tails."""
    if not s or not s.strip():
        return {}
    out: dict[str, list[str]] = defaultdict(list)
    for url_str in s.strip().split():
        u = urlparse(url_str)
        path = (u.path or "/").lstrip("/")
        first, _, rest = path.partition("/")
        key = f"{u.netloc}/{first}"
        if rest:
            out[key].append(rest)
    return dict(out)


def get_endpoint_from_requests(s: str) -> str | None:
    """Extract endpoint (first path component) from REQUESTS for transfer test."""
    if not s or not s.strip():
        return None
    url_str = s.strip().split()[0]
    u = urlparse(url_str)
    path = (u.path or "/").lstrip("/")
    first, _, _ = path.partition("/")
    return first if first else None


def load_files_for_endpoint(endpoint: str) -> dict[str, list[int]]:
    """Load files from /www/<endpoint>/ and return {filename: list of byte values}."""
    files = {}
    www_endpoint = os.path.join(WWW, endpoint)
    if not os.path.isdir(www_endpoint):
        return files
    for name in os.listdir(www_endpoint):
        path = os.path.join(www_endpoint, name)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                files[name] = list(f.read())
    return files


def exit_if_unsupported_testcase() -> None:
    """Exit with sentinel 127 if TESTCASE is not supported. Call before starting the browser."""
    testcase = os.environ.get("TESTCASE")
    if not testcase or testcase not in testcases:
        print(
            f"Unknown TESTCASE: '{testcase}'. TESTCASE must be one of: {', '.join(testcases.keys())}"
        )
        sys.exit(127)


def get_config() -> dict:
    """Read and validate env; return config dict. Exits on error."""
    testcase = os.environ.get("TESTCASE")
    if not testcase or testcase not in testcases:
        print(
            f"Unknown TESTCASE: '{testcase}'. TESTCASE must be one of: {', '.join(testcases.keys())}"
        )
        sys.exit(127)

    requests_str = os.environ.get("REQUESTS", "")
    requests_list = [r for r in requests_str.split(" ") if r]
    if not requests_list:
        print("REQUESTS must contain at least one URL")
        sys.exit(1)

    url = requests_list[0]
    protocols = os.environ["PROTOCOLS"].split(" ")
    certhash = os.environ["CERTHASH"]
    request_map = parse_client_requests(requests_str)
    filenames = next(iter(request_map.values()), []) if request_map else []

    config = {
        "testcase": testcase,
        "url": url,
        "protocols": protocols,
        "certhash": certhash,
        "request_map": request_map,
        "filenames": filenames,
    }

    if testcase == "transfer":
        endpoint = get_endpoint_from_requests(requests_str)
        if not endpoint:
            print("transfer test requires at least one request URL with endpoint path")
            sys.exit(1)
        config["endpoint"] = endpoint
        config["files_by_filename"] = load_files_for_endpoint(endpoint)

    if testcase in (
        "transfer-unidirectional-receive",
        "transfer-bidirectional-receive",
        "transfer-datagram-receive",
    ):
        endpoint = get_endpoint_from_requests(requests_str)
        if not endpoint:
            print(f"{testcase} requires at least one request URL with endpoint path")
            sys.exit(1)
        config["endpoint"] = endpoint

    return config


def run_test(driver) -> None:
    """Run the WebTransport test using the given Selenium WebDriver."""
    config = get_config()
    testcase = config["testcase"]
    url = config["url"]
    protocols = config["protocols"]
    certhash = config["certhash"]
    filenames = config["filenames"]

    driver.set_script_timeout(120)
    driver.get("file:///index.html")

    func_name = testcases[testcase]
    script = f"return {func_name}(...arguments);"

    if testcase == "transfer":
        result = driver.execute_script(
            script,
            url,
            certhash,
            protocols,
            config["files_by_filename"],
        )
    else:
        result = driver.execute_script(script, url, certhash, protocols, filenames)
        print(f"session established, negotiated protocol: {result['protocol']}")

    with open(DOWNLOADS + "negotiated_protocol.txt", "wb") as f:
        f.write(result["protocol"].encode("utf-8"))

    if testcase in (
        "transfer-unidirectional-receive",
        "transfer-bidirectional-receive",
        "transfer-datagram-receive",
    ):
        endpoint = config["endpoint"]
        download_dir = os.path.join(DOWNLOADS, endpoint)
        os.makedirs(download_dir, exist_ok=True)
        for filename, chunk in result["files"].items():
            raw = bytes(chunk)
            print(f"downloaded file: {filename}, size: {len(raw)}")
            full_path = os.path.join(download_dir, filename)
            with open(full_path, "wb") as f:
                f.write(raw)

    try:
        for entry in driver.get_log("browser"):
            print(entry)
    except Exception:
        pass  # Browser log not supported on all drivers (e.g. some Firefox setups)
