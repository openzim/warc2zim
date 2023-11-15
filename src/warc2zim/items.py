#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim's item classes

This module contains the differents Item we may want to add to a Zim archive.
"""

import logging
import re

import pkg_resources
from libzim.writer import Hint
from zimscraperlib.types import get_mime_for_name
from zimscraperlib.zim.items import StaticItem

from warc2zim.utils import get_record_url, get_record_mime_type
from warc2zim.content_rewriting import HtmlRewriter, CSSRewriter

# Shared logger
logger = logging.getLogger("warc2zim.items")

# external sw.js filename
SW_JS = "sw.js"

HEAD_INS = re.compile(b"(<head>)", re.I)
CSS_INS = re.compile(b"(</head>)", re.I)


class WARCPayloadItem(StaticItem):
    """WARCPayloadItem used to store the WARC payload
    Usually stored under A namespace
    """

    def __init__(self, path, record, head_insert, css_insert):
        super().__init__()
        self.record = record
        self.path = path
        self.mimetype = get_record_mime_type(record)
        self.title = ""

        if hasattr(self.record, "buffered_stream"):
            self.record.buffered_stream.seek(0)
            self.content = self.record.buffered_stream.read()
        else:
            self.content = self.record.content_stream().read()

        if self.mimetype.startswith("text/html"):
            self.title, self.content = HtmlRewriter(
                self.path, head_insert, css_insert
            ).rewrite(self.content)
        elif self.mimetype.startswith("text/css"):
            self.content = CSSRewriter(self.path).rewrite(self.content)

    def get_hints(self):
        is_front = self.mimetype.startswith("text/html")
        return {Hint.FRONT_ARTICLE: is_front}


class StaticArticle(StaticItem):
    def __init__(self, env, filename, main_url, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.main_url = main_url

        self.mime = get_mime_for_name(filename)
        self.mime = self.mime or "application/octet-stream"

        if filename != SW_JS:
            template = env.get_template(filename)
            self.content = template.render(MAIN_URL=self.main_url)
        else:
            self.content = pkg_resources.resource_string(
                "warc2zim", "templates/" + filename
            ).decode("utf-8")

    def get_path(self):
        return "_zim_static/" + self.filename

    def get_mimetype(self):
        return self.mime

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: False}
