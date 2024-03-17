#!/usr/bin/env python3

import argparse
import os
import array

from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--certhash", help="server certificate hash")
    return parser.parse_args()

DOWNLOADS = "/downloads/"

requests = os.environ["REQUESTS"].split(" ")

options = webdriver.ChromeOptions()
options.gpu = False
options.binary_location = "/usr/bin/google-chrome-beta"
options.add_argument("--no-sandbox")
options.add_argument("--log-net-log=/logs/chrome.json")
options.add_argument("--net-log-capture-mode=IncludeSensitive")
options.add_argument("--enable-experimental-web-platform-features")
options.add_argument("--enable-features=WebTransport,WebTransportHttp3")
options.add_argument("--headless=new")

o = urlparse(requests[0])
server = o.netloc
path = o.path

with open("script_template.js") as f:
    script = f.read()
script = script.replace("%%SERVER%%", server)
script = script.replace("%%TESTCASE%%", os.environ["TESTCASE"])
script = script.replace("%%CERTHASH%%", get_args().certhash)

with open('/script.js', 'w') as file:
    file.write(script)

with open('/index.html', 'w') as file:
    file.write("<html><head><script src='script.js'></script></head></html>")

service = Service(executable_path="/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)
driver.get("file:///index.html")
data = driver.execute_script("return request('" + path + "');")

a = array.array('B')
a.extend(data)
with open(DOWNLOADS + path, 'wb') as file:
    file.write(a)

driver.close()
