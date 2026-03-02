#!/bin/bash

/setup.sh

service dbus start

CERTHASH=$(openssl x509 -in /certs/cert.pem -outform DER | openssl dgst -sha256 -binary | base64)
echo "Certificate hash: $CERTHASH"
export CERTHASH

firefox --version

/wait-for-it.sh sim:57832 -s -t 30

python3 run_firefox.py
