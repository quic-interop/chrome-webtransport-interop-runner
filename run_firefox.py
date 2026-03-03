#!/usr/bin/env python3

import os
import signal

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

from run import exit_if_unsupported_testcase, run_test

exit_if_unsupported_testcase()

options = FirefoxOptions()
options.add_argument("--headless")
options.set_preference("network.http.http3.enabled", True)
options.set_preference("network.http.speculative-parallel-limit", 0)

driver = webdriver.Firefox(
    service=FirefoxService("/usr/bin/geckodriver"), options=options
)
try:
    run_test(driver)
finally:    
    # driver.quit() can hang with Firefox/geckodriver
    def _timeout(signum, frame):
        os._exit(0)
    signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(5)
    try:
        driver.quit()
    finally:
        signal.alarm(0)
