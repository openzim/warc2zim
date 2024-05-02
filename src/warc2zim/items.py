#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim's item classes

This module contains the differents Item we may want to add to a Zim archive.
"""

from pathlib import Path

from jinja2.environment import Template
from libzim.writer import Hint  # pyright: ignore[reportMissingImports]
from warcio.recordloader import ArcWarcRecord
from zimscraperlib.types import get_mime_for_name
from zimscraperlib.zim.items import StaticItem

from warc2zim.content_rewriting.generic import Rewriter
from warc2zim.url_rewriting import ZimPath
from warc2zim.utils import get_record_mime_type


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
        existing_zim_paths: set[ZimPath],
        missing_zim_paths: set[ZimPath] | None,
        js_modules: set[ZimPath],
    ):
        super().__init__()

        self.path = path
        self.mimetype = get_record_mime_type(record)
        (self.title, self.content) = Rewriter(
            path, record, existing_zim_paths, missing_zim_paths, js_modules
        ).rewrite(head_template, css_insert)

    def get_hints(self):
        is_front = self.mimetype.startswith("text/html")
        return {Hint.FRONT_ARTICLE: is_front}


class StaticArticle(StaticItem):
    def __init__(self, filename: Path, main_path: str, **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.main_path = main_path

        self.mime = get_mime_for_name(filename)
        self.mime = self.mime or "application/octet-stream"

        self.content = filename.read_text("utf-8")

    def get_path(self):
        return "_zim_static/" + self.filename.name

    def get_mimetype(self):
        return self.mime

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: False}
