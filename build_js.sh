#!/bin/bash

# Custom script to install Python on top of a Docker Node-JS image, then install
# required Python deps, generate fuzzy rules, and finally bundle JS script

apt-get update -y

apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv

rm -rf /var/lib/apt/lists/*

python3 -m venv /local

/local/bin/python -m pip install --no-cache-dir -U \
    pip \
    jinja2==3.1.3

/local/bin/python /src/rules/generate_rules.py

cd /src/javascript

OUTPUT_DIR=/output yarn build-prod
