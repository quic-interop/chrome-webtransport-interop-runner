#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from run import exit_if_unsupported_testcase, run_test

exit_if_unsupported_testcase()

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
try:
    run_test(driver)
finally:
    driver.quit()
