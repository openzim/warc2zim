from urllib.parse import urlsplit

from jinja2.environment import Template
from warcio.recordloader import ArcWarcRecord

from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.ds import build_domain_specific_rewriter
from warc2zim.content_rewriting.html import HtmlRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter
from warc2zim.utils import (
    get_record_content,
    get_record_encoding,
    get_record_mime_type,
    get_record_url,
    to_string,
)


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

        return ("", self.content)

    def get_rewrite_mode(self, record, mimetype):
        if getattr(record, "method", "GET") == "POST":
            return None
        if mimetype == "text/html":
            # TODO : Handle header "Accept" == "application/json"
            return "html"

        if mimetype == "text/css":
            return "css"

        if "javascript" in mimetype:
            return "javascript"

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

    def rewrite_css(self):
        return ("", CssRewriter(self.url_rewriter).rewrite(self.content))

    def rewrite_js(self, opts):
        rewriter = build_domain_specific_rewriter(self.path, self.url_rewriter)
        return (
            "",
            rewriter.rewrite(self.content_str, opts),
        )
