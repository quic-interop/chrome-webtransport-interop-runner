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

testcases = {
    "handshake": "runHandshake",
    "transfer-unidirectional-receive": "runTransferUnidirectional",
}

testcase = os.environ["TESTCASE"]

if testcase not in testcases:
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


requests = os.environ["REQUESTS"].split(" ")
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

o = urlparse(requests[0])
server = o.netloc
path = o.path

driver = webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
driver.set_script_timeout(120)
driver.get("file:///index.html")
func_name = testcases.get(testcase)
script = f"return {func_name}('{requests[0]}', '{certhash}', {json.dumps(protocols)}, {json.dumps(filenames)});"

try:
    data = driver.execute_script(script)
    print(f"session established, negotiated protocol: {data['protocol']}")
except Exception as e:
    print(f"execute_script failed: {e}")
    raise

with open(DOWNLOADS + "negotiated_protocol.txt", "wb") as f:
    f.write(data['protocol'].encode("utf-8"))

if testcase == "transfer-unidirectional-receive":
    for filename, chunk in data['files'].items():
        raw = bytes(chunk)
        print(f"downloaded file: {filename}, size: {len(raw)}")
        full_path = DOWNLOADS + filename
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(raw)

# for debugging, print all the console messages
for entry in driver.get_log("browser"):
    print(entry)

driver.quit()
