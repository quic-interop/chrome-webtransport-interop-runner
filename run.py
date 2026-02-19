#!/usr/bin/env python3

import json
import os
import sys
from collections import defaultdict
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

DOWNLOADS = "/downloads/"
WWW = "/www/"

testcases = {
    "handshake": "runHandshake",
    "transfer": "runTransfer",
    "transfer-unidirectional-receive": "runTransferUnidirectional",
}

testcase = os.environ["TESTCASE"]

if testcase not in testcases:
    print(f"Unknown TESTCASE: '{testcase}'. TESTCASE must be one of: {', '.join(testcases.keys())}")
    sys.exit(127)

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


requests_list = [r for r in os.environ["REQUESTS"].split(" ") if r]
if not requests_list:
    print("REQUESTS must contain at least one URL")
    sys.exit(1)
url = requests_list[0]
protocols = os.environ["PROTOCOLS"].split(",")
certhash = os.environ["CERTHASH"]
request_map = parse_client_requests(os.environ["REQUESTS"])
filenames = next(iter(request_map.values()), []) if request_map else []

options = webdriver.ChromeOptions()
options.binary_location = "/usr/bin/google-chrome-beta"
options.add_argument("--no-sandbox")
options.add_argument("--headless")
options.add_argument("--enable-quic")
options.add_argument("--disable-gpu")
options.add_argument("--disable-setuid-sandbox")
options.add_argument("--log-net-log=/logs/chrome.json")
options.add_argument("--net-log-capture-mode=IncludeSensitive")
options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
driver.set_script_timeout(120)
driver.get("file:///index.html")
func_name = testcases.get(testcase)
script = f"return {func_name}(...arguments);"

try:
    if testcase == "transfer":
        endpoint = get_endpoint_from_requests(os.environ["REQUESTS"])
        if not endpoint:
            print("transfer test requires at least one request URL with endpoint path")
            sys.exit(1)
        files_by_filename = load_files_for_endpoint(endpoint)
        result = driver.execute_script(script, url, certhash, protocols, files_by_filename)
    else:
        result = driver.execute_script(script, url, certhash, protocols, filenames)
        print(f"session established, negotiated protocol: {result['protocol']}")
except Exception as e:
    print(f"execute_script failed: {e}")
    raise

with open(DOWNLOADS + "negotiated_protocol.txt", "wb") as f:
    f.write(result['protocol'].encode("utf-8"))

if testcase == "transfer-unidirectional-receive":
    endpoint = get_endpoint_from_requests(os.environ["REQUESTS"])
    if not endpoint:
        print("transfer-unidirectional-receive requires at least one request URL with endpoint path")
        sys.exit(1)
    download_dir = os.path.join(DOWNLOADS, endpoint)
    os.makedirs(download_dir, exist_ok=True)
    for filename, chunk in result['files'].items():
        raw = bytes(chunk)
        print(f"downloaded file: {filename}, size: {len(raw)}")
        full_path = os.path.join(download_dir, filename)
        with open(full_path, "wb") as f:
            f.write(raw)

# for debugging, print all the console messages
for entry in driver.get_log("browser"):
    print(entry)

driver.quit()
