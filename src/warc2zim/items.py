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
        path: ZimPath,
        record: ArcWarcRecord,
        pre_head_template: Template,
        post_head_template: Template,
        existing_zim_paths: set[ZimPath],
        missing_zim_paths: set[ZimPath] | None,
        js_modules: set[ZimPath],
        charsets_to_try: list[str],
        content_header_bytes_length: int,
        *,
        ignore_content_header_charsets: bool,
        ignore_http_header_charsets: bool,
    ):
        super().__init__()

        self.path = path.value
        self.mimetype = get_record_mime_type(record)
        (self.title, self.content) = Rewriter(
            path,
            record,
            existing_zim_paths,
            missing_zim_paths,
            js_modules,
            charsets_to_try,
            content_header_bytes_length,
            ignore_content_header_charsets=ignore_content_header_charsets,
            ignore_http_header_charsets=ignore_http_header_charsets,
        ).rewrite(pre_head_template, post_head_template)

    def get_hints(self):
        is_front = self.mimetype.startswith("text/html") or self.mimetype.startswith(
            "application/pdf"
        )
        return {Hint.FRONT_ARTICLE: is_front}


class StaticArticle(StaticItem):
    """A file to store in _zim_static folder, based on exisiting file.

    Meant to be used for unknown mimetype which will be guessed
    """

    def __init__(self, filename: Path, main_path: str, **kwargs):
        super().__init__(auto_index=False, **kwargs)
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


class StaticFile(StaticItem):
    """A file to store in _zim_static folder, based on known content and mimetype"""

    def __init__(self, content: str | bytes, filename: str, mimetype: str):
        super().__init__(auto_index=False)
        self.filename = filename
        self.mime = mimetype
        self.content = content

    def get_path(self):
        return "_zim_static/" + self.filename

    def get_mimetype(self):
        return self.mime

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: False}
