from collections.abc import Callable

import pytest

from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.content_rewriting.js import JsRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath


@pytest.fixture(scope="module")
def no_js_notify():
    """Fixture to not care about notification of detection of a JS file"""

    def no_js_notify_handler(_: str):
        pass

    yield no_js_notify_handler


class SimpleUrlRewriter(ArticleUrlRewriter):
    """Basic URL rewriter mocking most calls"""

    def __init__(self, article_url: HttpUrl, suffix: str = ""):
        self.article_url = article_url
        self.suffix = suffix

    def __call__(
        self,
        item_url: str,
        base_href: str | None,  # noqa: ARG002
        *,
        rewrite_all_url: bool = True,  # noqa: ARG002
    ) -> str:
        return item_url + self.suffix

    def get_item_path(
        self, item_url: str, base_href: str | None  # noqa: ARG002
    ) -> ZimPath:
        return ZimPath("")

    def get_document_uri(
        self, item_path: ZimPath, item_fragment: str  # noqa: ARG002
    ) -> str:
        return ""


@pytest.fixture(scope="module")
def simple_url_rewriter():
    """Fixture to create a basic url rewriter returning URLs as-is"""

    def get_simple_url_rewriter(url: str, suffix: str = ""):
        return SimpleUrlRewriter(HttpUrl(url), suffix=suffix)

    yield get_simple_url_rewriter


@pytest.fixture(scope="module")
def js_rewriter():
    """Fixture to create a basic url rewriter returning URLs as-is"""

    def get_js_rewriter(
        url_rewriter: ArticleUrlRewriter,
        base_href: str | None,
        notify_js_module: Callable[[ZimPath], None],
    ):
        return JsRewriter(
            url_rewriter=url_rewriter,
            base_href=base_href,
            notify_js_module=notify_js_module,
        )

    yield get_js_rewriter


@pytest.fixture(scope="module")
def css_rewriter():
    """Fixture to create a basic url rewriter returning URLs as-is"""

    def get_css_rewriter(
        url_rewriter: ArticleUrlRewriter,
        base_href: str | None,
    ):
        return CssRewriter(
            url_rewriter=url_rewriter,
            base_href=base_href,
        )

    yield get_css_rewriter
