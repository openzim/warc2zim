#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim's item classes

This module contains the differents Item we may want to add to a Zim archive.
"""

from urllib.parse import urlsplit

import pkg_resources
from jinja2.environment import Template
from libzim.writer import Hint  # pyright: ignore
from warcio.recordloader import ArcWarcRecord
from zimscraperlib.types import get_mime_for_name
from zimscraperlib.zim.items import StaticItem

from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.html import HtmlRewriter
from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter
from warc2zim.utils import get_record_mime_type, get_record_url


class WARCPayloadItem(StaticItem):
    """WARCPayloadItem used to store the WARC payload
    Usually stored under A namespace
    """

    def __init__(
        self,
        path: str,
        record: ArcWarcRecord,
        head_template: Template,
        css_insert: str | None,
        known_urls: set[str],
    ):
        super().__init__()
        self.record = record
        self.path = path
        self.mimetype = get_record_mime_type(record)
        self.title = ""

        if hasattr(self.record, "buffered_stream"):
            self.record.buffered_stream.seek(0)  # pyright: ignore
            self.content = self.record.buffered_stream.read()  # pyright: ignore
        else:
            self.content = self.record.content_stream().read()

        if getattr(record, "method", "GET") == "POST":
            return

        orig_url_str = get_record_url(record)
        url_rewriter = ArticleUrlRewriter(orig_url_str, known_urls)

        if self.mimetype.startswith("text/html"):
            orig_url = urlsplit(orig_url_str)

            rel_static_prefix = url_rewriter.from_normalized("_zim_static/")
            head_insert = head_template.render(
                path=path,
                static_prefix=rel_static_prefix,
                orig_url=orig_url_str,
                orig_scheme=orig_url.scheme,
                orig_host=orig_url.netloc,
            )
            self.title, self.content = HtmlRewriter(
                url_rewriter, head_insert, css_insert
            ).rewrite(self.content)
        elif self.mimetype.startswith("text/css"):
            self.content = CssRewriter(url_rewriter).rewrite(self.content)
        elif "javascript" in self.mimetype:
            self.content = JsRewriter(url_rewriter).rewrite(self.content.decode())

    def get_hints(self):
        is_front = self.mimetype.startswith("text/html")
        return {Hint.FRONT_ARTICLE: is_front}


class StaticArticle(StaticItem):
    def __init__(self, filename, main_url, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.main_url = main_url

        self.mime = get_mime_for_name(filename)
        self.mime = self.mime or "application/octet-stream"

        self.content = pkg_resources.resource_string(
            "warc2zim", "statics/" + filename
        ).decode("utf-8")

    def get_path(self):
        return "_zim_static/" + self.filename

    def get_mimetype(self):
        return self.mime

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: False}
