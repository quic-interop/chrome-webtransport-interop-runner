#!/usr/bin/env python3

import argparse
import os
import array
import sys
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

DOWNLOADS = "/downloads/"

requests = os.environ["REQUESTS"].split(" ")
protocols = os.environ["PROTOCOLS"].split(",")
certhash = os.environ["CERTHASH"]

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
driver.set_script_timeout(30)
driver.get("file:///index.html")
script = (
    "return establishSession('" + requests[0] + "', '" + certhash + "', "
    + '[' + ', '.join("'" + p.strip() + "'" for p in protocols) + ']'
    + ");"
)
try:
    data = driver.execute_script(script)
    print(f"session established, negotiated protocol: {data}")
except Exception as e:
    print(f"execute_script failed: {e}")
    raise

with open(DOWNLOADS + "negotiated_protocol.txt", "wb") as f:
    f.write(data.encode("utf-8"))

# for debugging, print all the console messages
for entry in driver.get_log("browser"):
    print(entry)

driver.quit()
