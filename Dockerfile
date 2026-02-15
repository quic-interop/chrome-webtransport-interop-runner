FROM martenseemann/quic-network-simulator-endpoint:latest AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y wget gnupg2
RUN mkdir -p /etc/apt/keyrings && \
  wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
RUN echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list

RUN apt-get update && \
  apt-get install -y python3 python3-pip unzip google-chrome-beta && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages selenium

ENV CHROMEDRIVER_VERSION="146.0.7680.0"
RUN wget -q "https://storage.googleapis.com/chrome-for-testing-public/$CHROMEDRIVER_VERSION/linux64/chromedriver-linux64.zip" && \
  unzip chromedriver-linux64.zip && \
  mv chromedriver-linux64/chromedriver /usr/bin && \
  chmod +x /usr/bin/chromedriver && \
  rm chromedriver-linux64.zip

COPY script.js index.html run.py run_endpoint.sh /

ENTRYPOINT [ "/run_endpoint.sh" ]
