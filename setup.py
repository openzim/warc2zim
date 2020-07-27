#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import pathlib
from setuptools import setup, find_packages

root_dir = pathlib.Path(__file__).parent


def read(*names, **kwargs):
    with open(root_dir.joinpath(*names), "r") as fh:
        return fh.read()


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
    zip_safe=True,
    include_package_data=True,
    data_files={
        "requirements.txt": "requirements.txt",
        "src/warc2zim/VERSION": root_dir.joinpath("src", "warc2zim", "VERSION"),
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
