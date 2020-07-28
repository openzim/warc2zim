FROM python:3.8

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends locales-all \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY src /src/warc2zim/src
COPY requirements.txt setup.py README.md LICENSE MANIFEST.in /src/warc2zim/
RUN cd /src/warc2zim && python3 ./setup.py install

RUN mkdir -p /output
WORKDIR /output
CMD ["warc2zim", "--help"]
