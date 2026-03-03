# Browser Images for the WebTransport Interop Runner

This repository provides [Interop Runner](https://github.com/quic-interop/quic-interop-runner) images for **Chrome** and **Firefox**, for running WebTransport interop tests in either browser.

## Chrome image

The Chrome image uses the [Dev Channel](https://www.chromium.org/getting-involved/dev-channel) release for Linux. Chrome is controlled by [Selenium](https://www.selenium.dev/) using [ChromeDriver](https://chromedriver.chromium.org/).

## Firefox image

The Firefox image uses Firefox from [Mozilla’s APT repository](https://packages.mozilla.org/apt). Firefox is controlled by [Selenium](https://www.selenium.dev/) using [GeckoDriver](https://github.com/mozilla/geckodriver).

## Building the images

Build the Chrome image with:

```bash
docker build -f Dockerfile_chrome -t chrome-webtransport-interop .
```

Build the Firefox image with:

```bash
docker build -f Dockerfile_firefox -t firefox-webtransport-interop .
```
