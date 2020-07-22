#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

from setuptools import setup, find_packages

__version__ = '0.1.0'

setup(
    name="warc2zim",
    version=__version__,
    description="Convert WARC to ZIM",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Webrecorder Software",
    author_email="info@webrecorder.net",
    url="https://github.com/openzim/warc2zim",
    packages=find_packages(exclude=['tests']),
    provides=['warc2zim'],
    install_requires=[
        'warcio',
        'libzim',
    ],
    zip_safe=True,
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
