from urllib.parse import urljoin

import pytest

from warc2zim.url_rewriting import ArticleUrlRewriter


@pytest.fixture(
    params=[
        "https://kiwix.org/a/article/path",
        "https://kiwix.org/a/article/path/",
        "https://kiwix.org/a/path",
        "https://kiwix.org/a/path/",
    ]
)
def rewriter(request):
    yield ArticleUrlRewriter(request.param, {"kiwix.org/bar/foo"})


def test_relative_url(rewriter):
    for url in ["foo", "bar/foo", "foo/", "bar/foo/", "../baz"]:
        assert rewriter(url) == url
        assert rewriter("./" + url) == url
        assert urljoin(rewriter.article_url, rewriter(url)) == urljoin(
            rewriter.article_url, url
        )

    if rewriter.article_url == "https://kiwix.org/a/path":
        # While it may seems wrong from a path point of view,
        # it is valid from a url side when going up to the `<host>/` is "no op".
        assert rewriter("../../biz") == "../biz"
    else:
        assert rewriter("../../biz") == "../../biz"
        assert rewriter("./../../biz") == "../../biz"


def test_absolute_path_url(rewriter):
    for url in ["/foo", "/foo/bar"]:
        for input_url in [url, f" {url}", f"{url} ", f" {url} "]:
            rewriten = rewriter(input_url)
            # Must produce a relative link.
            assert not rewriten.startswith("/")
            # Relative link must be resolved to a absolute url in the same domain than
            # article_url.
            assert urljoin(rewriter.article_url, rewriten) == "https://kiwix.org" + url


def test_absolute_scheme_url(rewriter):
    # We will serve our content from serving.com (moving kiwix.org as the first part of
    # the path).
    serving_address = rewriter.article_url.replace("kiwix.org", "serving.com/kiwix.org")

    for url in ["//exemple.com/foo", "//exemple.com/foo/bar", "//kiwix.org/baz"]:
        rewriten = rewriter(url)
        # Must produce a relative link.
        assert not rewriten.startswith("/")
        # Relative link must be resolved to a absolute url in the serving domain with a
        # path containing article_url's host.
        assert urljoin(serving_address, rewriten) == "https://serving.com" + url[1:]


def test_absolute_url(rewriter):
    # We will serve our content from serving.com (moving kiwix.org as the first part of
    # the path).
    serving_address = rewriter.article_url.replace("kiwix.org", "serving.com/kiwix.org")

    for url in [
        "https://exemple.com/foo",
        "http://exemple.com/foo/bar",
        "http://kiwix.org/baz",
    ]:
        rewriten = rewriter(url)
        # Must produce a relative link
        assert not rewriten.startswith("/")
        # Relative link must be resolved to a absolute url in the serving domain with a
        # path containing article_url's host.
        # We don't care about scheme, always use what we are serving from.
        assert (
            urljoin(serving_address, rewriten)
            == "https://serving.com" + url.split(":", 1)[1][1:]
        )


def test_no_rewrite_blob_data(rewriter):
    for url in ["data:0548datacontent", "blob:exemple.com/url"]:
        assert rewriter(url) == url


def test_no_rewrite_external_link(rewriter):
    for rewrite_all_url in [True, False]:
        # We always rewrite "internal" urls
        assert "kiwix.org" not in rewriter(
            "https://kiwix.org/bar/foo", rewrite_all_url=rewrite_all_url
        )

    # External urls are only rewriten if 'rewrite_all_url' is True
    assert "kiwix.org" not in rewriter(
        "https://kiwix.org/external/link", rewrite_all_url=True
    )
    assert (
        rewriter("https://kiwix.org/external/link", rewrite_all_url=False)
        == "https://kiwix.org/external/link"
    )
