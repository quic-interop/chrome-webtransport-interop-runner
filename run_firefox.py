#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

from run import exit_if_unsupported_testcase, run_test

exit_if_unsupported_testcase()

options = FirefoxOptions()
options.add_argument("--headless")
options.set_preference("network.http.http3.enabled", True)
options.set_preference("network.http.http3.enable_0rtt", True)

driver = webdriver.Firefox(
    service=FirefoxService("/usr/bin/geckodriver"), options=options
)
try:
    run_test(driver)
finally:
    driver.quit()
