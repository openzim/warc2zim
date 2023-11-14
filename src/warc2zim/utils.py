#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import pkg_resources
from bs4 import BeautifulSoup


def get_version():
    return pkg_resources.get_distribution("warc2zim").version


def get_record_url(record):
    """Check if record has url converted from POST/PUT, and if so, use that
    otherwise return the target url"""
    if hasattr(record, "urlkey"):
        return record.urlkey
    return record.rec_headers["WARC-Target-URI"]


def get_record_mime_type(record):
    if record.http_headers:
        # if the record has HTTP headers, use the Content-Type from those
        # (eg. 'response' record)
        content_type = record.http_headers["Content-Type"]
    else:
        # otherwise, use the Content-Type from WARC headers
        content_type = record.rec_headers["Content-Type"]

    mime = content_type or ""
    return mime.split(";")[0]


def parse_title(content):
    try:
        soup = BeautifulSoup(content, "html.parser")
        return soup.title.text or ""
    except Exception:
        return ""


def to_string(input: str | bytes) -> str:
    try:
        input = input.decode("utf8")
    except AttributeError:
        pass
    return input
