import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from jinja2.environment import Template
from warcio.recordloader import ArcWarcRecord

from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.ds import get_ds_rules
from warc2zim.content_rewriting.html import HtmlRewriter
from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.content_rewriting.rx_replacer import RxRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter
from warc2zim.utils import (
    get_record_content,
    get_record_encoding,
    get_record_mime_type,
    get_record_url,
    to_string,
)

# Parse JSONP. This match "anything" preceded by space or comments
JSONP_REGEX = re.compile(
    r"^(?:\s*(?:(?:\/\*[^*]*\*\/)|(?:\/\/[^\n]+[\n])))*\s*([\w.]+)\([{[]"
)
JSONP_CALLBACK_REGEX = re.compile(r"[?].*(?:callback|jsonp)=([^&]+)", re.I)


def no_title(
    function: Callable[..., str | bytes]
) -> Callable[..., tuple[str, str | bytes]]:
    """Decorator for methods transforming content without extracting a title.

    The generic rewriter return a title to use as item title but most
    content don't have a title. Such rewriter just rewrite content and do not
    extract a title, but the general API of returning a title must be fulfilled.

    This decorator takes a rewriter method not returning a title and make it return
    an empty title.
    """

    def rewrite(*args, **kwargs) -> tuple[str, str | bytes]:
        return ("", function(*args, **kwargs))

    return rewrite


def extract_jsonp_callback(url: str):
    callback = JSONP_CALLBACK_REGEX.match(url)
    if not callback or callback.group(1) == "?":
        return None

    return callback.group(1)


class Rewriter:
    def __init__(
        self,
        path: str,
        record: ArcWarcRecord,
        known_urls: set[str],
    ):
        self.content = get_record_content(record)

        mimetype = get_record_mime_type(record)

        self.encoding = get_record_encoding(record)

        self.path = path
        self.orig_url_str = get_record_url(record)
        self.url_rewriter = ArticleUrlRewriter(self.orig_url_str, known_urls)

        self.rewrite_mode = self.get_rewrite_mode(record, mimetype)

    @property
    def content_str(self):
        try:
            return to_string(self.content, self.encoding)
        except ValueError as e:
            raise RuntimeError(f"Impossible to decode item {self.path}") from e

    def rewrite(
        self, head_template: Template, css_insert: str | None
    ) -> tuple[str, str | bytes]:
        opts = {}

        if self.rewrite_mode == "html":
            return self.rewrite_html(head_template, css_insert)

        if self.rewrite_mode == "css":
            return self.rewrite_css()

        if self.rewrite_mode == "javascript":
            return self.rewrite_js(opts)

        if self.rewrite_mode == "jsonp":
            return self.rewrite_jsonp()

        if self.rewrite_mode == "json":
            return self.rewrite_json()

        return ("", self.content)

    def get_rewrite_mode(self, record, mimetype):
        if mimetype == "text/html":
            if getattr(record, "method", "GET") == "POST":
                return None

            # TODO : Handle header "Accept" == "application/json"
            return "html"

        if mimetype == "text/css":
            return "css"

        if mimetype in [
            "text/javascript",
            "application/javascript",
            "application/x-javascript",
        ]:
            if extract_jsonp_callback(self.orig_url_str):
                return "jsonp"

            if self.path.endswith(".json"):
                return "json"
            return "javascript"

        if mimetype == "application/json":
            return "json"

        return None

    def rewrite_html(self, head_template: Template, css_insert: str | None):
        orig_url = urlsplit(self.orig_url_str)

        rel_static_prefix = self.url_rewriter.from_normalized("_zim_static/")
        head_insert = head_template.render(
            path=self.path,
            static_prefix=rel_static_prefix,
            orig_url=self.orig_url_str,
            orig_scheme=orig_url.scheme,
            orig_host=orig_url.netloc,
        )
        return HtmlRewriter(self.url_rewriter, head_insert, css_insert).rewrite(
            self.content_str
        )

    @no_title
    def rewrite_css(self) -> str | bytes:
        return CssRewriter(self.url_rewriter).rewrite(self.content)

    @no_title
    def rewrite_js(self, opts: dict[str, Any]) -> str | bytes:
        ds_rules = get_ds_rules(self.orig_url_str)
        rewriter = JsRewriter(self.url_rewriter, ds_rules)
        return rewriter.rewrite(self.content.decode(), opts)

    @no_title
    def rewrite_jsonp(self) -> str | bytes:
        content = self.content.decode()
        match = JSONP_REGEX.match(content)
        if not match:
            return content

        callback = extract_jsonp_callback(self.orig_url_str)

        if not callback:
            return content

        return callback + match.group(1)

    @no_title
    def rewrite_json(self) -> str | bytes:
        content = self.rewrite_jsonp()[1]
        ds_rules = get_ds_rules(self.orig_url_str)
        if not ds_rules:
            return content

        rewriter = RxRewriter(ds_rules)
        return rewriter.rewrite(content, {})
