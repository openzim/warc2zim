import pytest

from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath


@pytest.fixture(scope="module")
def no_js_notify():
    """Fixture to not care about notification of detection of a JS file"""

    def no_js_notify_handler(_: str):
        pass

    yield no_js_notify_handler


class SimpleUrlRewriter(ArticleUrlRewriter):
    """Basic URL rewriter mocking most calls"""

    def __init__(self, article_url: HttpUrl):
        self.article_url = article_url

    def __call__(
        self,
        item_url: str,
        base_href: str | None,  # noqa: ARG002
        *,
        rewrite_all_url: bool = True,  # noqa: ARG002
    ) -> str:
        return item_url

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

    def get_simple_url_rewriter(url: str):
        return SimpleUrlRewriter(HttpUrl(url))

    yield get_simple_url_rewriter
