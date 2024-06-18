""" MIA English exclude list

This utility computes the list of all subpages/languages that must be ignored for the
English ZIM of The Marxists Internet Archive (MIA) at www.marxists.org.

Sample usage:
python contrib/marxists.org.py

Output: portion of the regex to use as exclude criteria in English recipe configuration.

"""

import re

import requests
from bs4 import BeautifulSoup

resp = requests.get("https://www.marxists.org/xlang/index.htm", timeout=10)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

subfolders = set()
REGEX = re.compile(r"\.\.\/(?P<subfolder>.*?)\/")
for anchor in soup.find_all("a"):
    if not anchor.has_attr("href"):
        continue
    if match := REGEX.match(anchor["href"]):
        subfolders.add(match.group("subfolder"))

print("|".join(sorted(subfolders)))  # noqa: T201
