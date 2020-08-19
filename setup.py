#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import pathlib
import urllib.request
from setuptools import setup, find_packages

root_dir = pathlib.Path(__file__).parent


def read(*names, **kwargs):
    with open(root_dir.joinpath(*names), "r") as fh:
        return fh.read()


REPLAY_SOURCE_URL = "https://cdn.jsdelivr.net/npm/@webrecorder/wabac@2.1.0-beta.0/dist/"


def download_replay(name):
    print("Downloading " + REPLAY_SOURCE_URL + name)
    with urllib.request.urlopen(REPLAY_SOURCE_URL + name) as response:
        with open(root_dir.joinpath("src", "warc2zim", "templates", name), "wb") as fh:
            fh.write(response.read())


download_replay("sw.js")


def get_package_data():
    pkgs = ["templates/*"]

    package_path = root_dir / "src" / "warc2zim"
    for path in package_path.glob("locale/*/LC_MESSAGES/*.mo"):
        pkgs.append(str(path.relative_to(package_path)))

    return pkgs


setup(
    name="warc2zim",
    version=read("src", "warc2zim", "VERSION").strip(),
    description="Convert WARC to ZIM",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    author="Webrecorder Software",
    author_email="info@webrecorder.net",
    url="https://github.com/openzim/warc2zim",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        line.strip()
        for line in read("requirements.txt").splitlines()
        if not line.strip().startswith("#")
    ],
    zip_safe=False,
    package_data={"warc2zim": get_package_data()},
    data_files={
        "requirements.txt": "requirements.txt",
        "src/warc2zim/VERSION": root_dir.joinpath("src", "warc2zim", "VERSION"),
    },
    message_extractors={
        ".": [
            (
                "src/warc2zim/templates/**",
                "jinja2",
                {"extensions": "jinja2.ext.autoescape,jinja2.ext.with_"},
            )
        ],
    },
    entry_points="""
        [console_scripts]
        warc2zim = warc2zim.main:warc2zim
    """,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    ],
    python_requires=">=3.6",
)
