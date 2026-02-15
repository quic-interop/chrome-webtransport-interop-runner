#!/bin/bash

# Set up the routing needed for the simulation.
/setup.sh

if [ ! -z "$TESTCASE" ]; then
    case "$TESTCASE" in
        "handshake") ;;
        *) exit 127 ;;
    esac
fi

service dbus start

CERTHASH=$(openssl x509 -in /certs/cert.pem -outform DER | openssl dgst -sha256 -binary | base64)
echo "Certificate hash: $CERTHASH"
export CERTHASH

google-chrome-beta --version

/wait-for-it.sh sim:57832 -s -t 30

python3 run.py
