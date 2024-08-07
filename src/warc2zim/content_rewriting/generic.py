import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlsplit

from jinja2.environment import Template
from warcio.recordloader import ArcWarcRecord

from warc2zim.constants import logger
from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.html import HtmlRewriter
from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath
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
        path: ZimPath,
        record: ArcWarcRecord,
        existing_zim_paths: set[ZimPath],
        missing_zim_paths: set[ZimPath] | None,
        js_modules: set[ZimPath],
        charsets_to_try: list[str],
        content_header_bytes_length: int,
        *,
        ignore_content_header_charsets: bool,
        ignore_http_header_charsets: bool,
    ):
        self.content = get_record_content(record)

        mimetype = get_record_mime_type(record)

        self.encoding = get_record_encoding(record)

        self.path = path
        self.orig_url_str = get_record_url(record)
        self.url_rewriter = ArticleUrlRewriter(
            HttpUrl(self.orig_url_str), existing_zim_paths, missing_zim_paths
        )

        self.rewrite_mode = self.get_rewrite_mode(record, mimetype)
        self.js_modules = js_modules
        self.charsets_to_try = charsets_to_try
        self.content_header_bytes_length = content_header_bytes_length
        self.ignore_content_header_charsets = ignore_content_header_charsets
        self.ignore_http_header_charsets = ignore_http_header_charsets

    @property
    def content_str(self) -> str:
        return to_string(
            self.content,
            self.encoding,
            self.charsets_to_try,
            self.content_header_bytes_length,
            ignore_content_header_charsets=(
                self.rewrite_mode != "html" or self.ignore_content_header_charsets
            ),
            ignore_http_header_charsets=self.ignore_http_header_charsets,
        )

    def rewrite(
        self, pre_head_template: Template, post_head_template: Template
    ) -> tuple[str, str | bytes]:
        opts = {}

        if self.rewrite_mode == "html":
            return self.rewrite_html(pre_head_template, post_head_template)

        if self.rewrite_mode == "css":
            return self.rewrite_css()

        if self.rewrite_mode == "javascript":
            if any(path == self.path for path in self.js_modules):
                opts["isModule"] = True
            return self.rewrite_js(opts)

        if self.rewrite_mode == "jsonp":
            return self.rewrite_jsonp()

        if self.rewrite_mode == "json":
            return self.rewrite_json()

        return ("", self.content)

    def get_rewrite_mode(self, record, mimetype):
        """Get current record rewrite mode

        The rewrite mode is used to decide which kind of resource we have (html, css,
        js, ...) and this is used to decide how it should be parsed and rewritten.
        """
        mimetype_rewrite_mode = self.get_mimetype_rewrite_mode(record, mimetype)

        resourcetype = record.rec_headers["WARC-Resource-Type"]
        if not resourcetype:
            return mimetype_rewrite_mode  # fallback for WARCs without resource type
        if not isinstance(resourcetype, str):
            raise Exception(f"Unsupported resourcetype class: {type(resourcetype)}")
        resourcetype = resourcetype.lower().strip()

        resourcetype_rewrite_mode = self.get_resourcetype_rewrite_mode(
            record, resourcetype, mimetype
        )

        if mimetype_rewrite_mode != resourcetype_rewrite_mode:
            logger.warning(
                f"Rewrite mode has changed in 2.0.1 for {self.path.value} record: was "
                f"{mimetype_rewrite_mode}, now is {resourcetype_rewrite_mode} ("
                f"mimetype: {mimetype}, resourcetype: {resourcetype})"
            )

        return resourcetype_rewrite_mode

    def get_resourcetype_rewrite_mode(self, record, resourcetype, mimetype):
        """Get current record rewrite mode based on WARC-Resource-Type and mimetype"""

        if resourcetype in ["document", "xhr"] and mimetype == "text/html":
            # TODO : Handle header "Accept" == "application/json"
            if getattr(record, "method", "GET") == "GET":
                return "html"

            return None

        if resourcetype == "stylesheet":
            return "css"

        if resourcetype in ["script", "fetch", "other", "xhr", "manifest"] and (
            mimetype == "application/json" or self.path.value.endswith(".json")
        ):
            return "json"

        if resourcetype in ["script", "other", "xhr"] and mimetype in [
            "text/javascript",
            "application/javascript",
            "application/x-javascript",
        ]:
            if extract_jsonp_callback(self.orig_url_str):
                return "jsonp"

            return "javascript"

        return None

    def get_mimetype_rewrite_mode(self, record, mimetype):
        """Get current record rewrite mode based on mimetype"""

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

            if self.path.value.endswith(".json"):
                return "json"
            return "javascript"

        if mimetype == "application/json":
            return "json"

        return None

    def js_module_found(self, zim_path: ZimPath):
        """Notification helper, for rewriters to call when they have found a JS module

        They call it with the JS module expected ZIM path since they are the only one
        to know the current document URL/path + the JS module URL.
        """
        self.js_modules.add(zim_path)

    def rewrite_html(self, pre_head_template: Template, post_head_template: Template):
        orig_url = urlsplit(self.orig_url_str)

        rel_static_prefix = self.url_rewriter.get_document_uri(
            ZimPath("_zim_static/"), ""
        )
        pre_head_insert = pre_head_template.render(
            path=quote(self.path.value),
            static_prefix=rel_static_prefix,
            orig_url=self.orig_url_str,
            orig_scheme=orig_url.scheme,
            orig_host=orig_url.netloc,
        )
        post_head_insert = post_head_template.render(
            path=quote(self.path.value),
            static_prefix=rel_static_prefix,
            orig_url=self.orig_url_str,
            orig_scheme=orig_url.scheme,
            orig_host=orig_url.netloc,
        )
        return HtmlRewriter(
            url_rewriter=self.url_rewriter,
            pre_head_insert=pre_head_insert,
            post_head_insert=post_head_insert,
            notify_js_module=self.js_module_found,
        ).rewrite(self.content_str)

    @no_title
    def rewrite_css(self) -> str | bytes:
        return CssRewriter(self.url_rewriter, base_href=None).rewrite(self.content_str)

    @no_title
    def rewrite_js(self, opts: dict[str, Any]) -> str | bytes:
        rewriter = JsRewriter(
            url_rewriter=self.url_rewriter,
            notify_js_module=self.js_module_found,
            base_href=None,
        )
        return rewriter.rewrite(self.content_str, opts)

    @no_title
    def rewrite_jsonp(self) -> str | bytes:
        content = self.content_str
        match = JSONP_REGEX.match(content)
        if not match:
            return content

        callback = extract_jsonp_callback(self.orig_url_str)

        if not callback:
            return content

        return callback + match.group(1)

    @no_title
    def rewrite_json(self) -> str | bytes:
        return self.rewrite_jsonp()[1]
