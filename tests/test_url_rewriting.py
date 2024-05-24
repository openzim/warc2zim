import pytest

from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath


@pytest.mark.parametrize(
    "article_url, original_content_url, expected_rewriten_content_url, know_paths, "
    "rewrite_all_url",
    [
        (
            "https://kiwix.org/a/article/document.html",
            "foo.html",
            "foo.html",
            ["kiwix.org/a/article/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo.html#anchor1",
            "foo.html#anchor1",
            ["kiwix.org/a/article/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo.html?foo=bar",
            "foo.html%3Ffoo%3Dbar",
            ["kiwix.org/a/article/foo.html?foo=bar"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo.html?foo=b%24ar",
            "foo.html%3Ffoo%3Db%24ar",
            ["kiwix.org/a/article/foo.html?foo=b$ar"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo.html?foo=b%3Far",  # a query string with an encoded ? char in value
            "foo.html%3Ffoo%3Db%3Far",
            ["kiwix.org/a/article/foo.html?foo=b?ar"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "fo%o.html",
            "fo%25o.html",
            ["kiwix.org/a/article/fo%o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foé.html",  # URL not matching RFC 3986 (many HTML documents are invalid)
            "fo%C3%A9.html",  # character is encoded so that URL match RFC 3986
            ["kiwix.org/a/article/foé.html"],  # but ZIM path is non-encoded
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "./foo.html",
            "foo.html",
            ["kiwix.org/a/article/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "../foo.html",
            "https://kiwix.org/a/foo.html",  # Full URL since not in known URLs
            ["kiwix.org/a/article/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "../foo.html",
            "../foo.html",  # all URLs rewrite activated
            ["kiwix.org/a/article/foo.html"],
            True,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "../foo.html",
            "../foo.html",
            ["kiwix.org/a/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "../bar/foo.html",
            "https://kiwix.org/a/bar/foo.html",  # Full URL since not in known URLs
            ["kiwix.org/a/article/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "../bar/foo.html",
            "../bar/foo.html",  # all URLs rewrite activated
            ["kiwix.org/a/article/foo.html"],
            True,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "../bar/foo.html",
            "../bar/foo.html",
            ["kiwix.org/a/bar/foo.html"],
            False,
        ),
        (  # we cannot go upper than host, so '../' in excess are removed
            "https://kiwix.org/a/article/document.html",
            "../../../../../foo.html",
            "../../foo.html",
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo?param=value",
            "foo%3Fparam%3Dvalue",
            ["kiwix.org/a/article/foo?param=value"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo?param=value%2F",
            "foo%3Fparam%3Dvalue/",
            ["kiwix.org/a/article/foo?param=value/"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo?param=value%2Fend",
            "foo%3Fparam%3Dvalue/end",
            ["kiwix.org/a/article/foo?param=value/end"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "foo/",
            "foo/",
            ["kiwix.org/a/article/foo/"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo o.html",
            "../../fo%20o.html",
            ["kiwix.org/fo o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo+o.html",
            "../../fo%2Bo.html",
            ["kiwix.org/fo+o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo%2Bo.html",
            "../../fo%2Bo.html",
            ["kiwix.org/fo+o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/foo.html?param=val+ue",
            "../../foo.html%3Fparam%3Dval%20ue",
            ["kiwix.org/foo.html?param=val ue"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo~o.html",
            "../../fo~o.html",
            ["kiwix.org/fo~o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo-o.html",
            "../../fo-o.html",
            ["kiwix.org/fo-o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo_o.html",
            "../../fo_o.html",
            ["kiwix.org/fo_o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo%7Eo.html",  # must not be encoded / must be decoded (RFC 3986 #2.3)
            "../../fo~o.html",
            ["kiwix.org/fo~o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo%2Do.html",  # must not be encoded / must be decoded (RFC 3986 #2.3)
            "../../fo-o.html",
            ["kiwix.org/fo-o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/fo%5Fo.html",  # must not be encoded / must be decoded (RFC 3986 #2.3)
            "../../fo_o.html",
            ["kiwix.org/fo_o.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/foo%2Ehtml",  # must not be encoded / must be decoded (RFC 3986 #2.3)
            "../../foo.html",
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "#anchor1",
            "#anchor1",
            ["kiwix.org/a/article/document.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/",
            "#anchor1",
            "#anchor1",
            ["kiwix.org/a/article/"],
            False,
        ),
        (
            "https://kiwix.org/a/article/",
            "../article/",
            "./",
            ["kiwix.org/a/article/"],
            False,
        ),
    ],
)
def test_relative_url(
    article_url,
    know_paths,
    original_content_url,
    expected_rewriten_content_url,
    rewrite_all_url,
):
    article_url = HttpUrl(article_url)
    rewriter = ArticleUrlRewriter(
        article_url,
        {ZimPath(path) for path in know_paths},
    )
    assert (
        rewriter(original_content_url, base_href=None, rewrite_all_url=rewrite_all_url)
        == expected_rewriten_content_url
    )


@pytest.mark.parametrize(
    "article_url, original_content_url, expected_rewriten_content_url, know_paths, "
    "rewrite_all_url",
    [
        (
            "https://kiwix.org/a/article/document.html",
            "/foo.html",
            "../../foo.html",
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/bar.html",
            "https://kiwix.org/bar.html",  # Full URL since not in known URLs
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "/bar.html",
            "../../bar.html",  # all URLs rewrite activated
            ["kiwix.org/foo.html"],
            True,
        ),
    ],
)
def test_absolute_path_url(
    article_url,
    know_paths,
    original_content_url,
    expected_rewriten_content_url,
    rewrite_all_url,
):
    article_url = HttpUrl(article_url)
    rewriter = ArticleUrlRewriter(
        article_url,
        {ZimPath(path) for path in know_paths},
    )
    assert (
        rewriter(original_content_url, base_href=None, rewrite_all_url=rewrite_all_url)
        == expected_rewriten_content_url
    )


@pytest.mark.parametrize(
    "article_url, original_content_url, expected_rewriten_content_url, know_paths, "
    "rewrite_all_url",
    [
        (
            "https://kiwix.org/a/article/document.html",
            "//kiwix.org/foo.html",
            "../../foo.html",
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "//kiwix.org/bar.html",
            "https://kiwix.org/bar.html",  # Full URL since not in known URLs
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "//kiwix.org/bar.html",
            "../../bar.html",  # all URLs rewrite activated
            ["kiwix.org/foo.html"],
            True,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "//acme.com/foo.html",
            "../../../acme.com/foo.html",
            ["acme.com/foo.html"],
            False,
        ),
        (
            "http://kiwix.org/a/article/document.html",
            "//acme.com/bar.html",
            "http://acme.com/bar.html",  # Full URL since not in known URLs
            ["kiwix.org/foo.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "//acme.com/bar.html",
            "../../../acme.com/bar.html",  # all URLs rewrite activated
            ["kiwix.org/foo.html"],
            True,
        ),
        (  # puny-encoded host is transformed into url-encoded value
            "https://kiwix.org/a/article/document.html",
            "//xn--exmple-cva.com/a/article/document.html",
            "../../../ex%C3%A9mple.com/a/article/document.html",
            ["exémple.com/a/article/document.html"],
            False,
        ),
        (  # host who should be puny-encoded ir transformed into url-encoded value
            "https://kiwix.org/a/article/document.html",
            "//exémple.com/a/article/document.html",
            "../../../ex%C3%A9mple.com/a/article/document.html",
            ["exémple.com/a/article/document.html"],
            False,
        ),
    ],
)
def test_absolute_scheme_url(
    article_url,
    know_paths,
    original_content_url,
    expected_rewriten_content_url,
    rewrite_all_url,
):
    article_url = HttpUrl(article_url)
    rewriter = ArticleUrlRewriter(
        article_url,
        {ZimPath(path) for path in know_paths},
    )
    assert (
        rewriter(original_content_url, base_href=None, rewrite_all_url=rewrite_all_url)
        == expected_rewriten_content_url
    )


@pytest.mark.parametrize(
    "article_url, original_content_url, expected_rewriten_content_url, know_paths, "
    "rewrite_all_url",
    [
        (
            "https://kiwix.org/a/article/document.html",
            "https://foo.org/a/article/document.html",
            "../../../foo.org/a/article/document.html",
            ["foo.org/a/article/document.html"],
            False,
        ),
        (
            "https://kiwix.org/a/article/document.html",
            "http://foo.org/a/article/document.html",
            "../../../foo.org/a/article/document.html",
            ["foo.org/a/article/document.html"],
            False,
        ),
        (
            "http://kiwix.org/a/article/document.html",
            "https://foo.org/a/article/document.html",
            "../../../foo.org/a/article/document.html",
            ["foo.org/a/article/document.html"],
            False,
        ),
        (
            "http://kiwix.org/a/article/document.html",
            "https://user:password@foo.org:8080/a/article/document.html",
            "../../../foo.org/a/article/document.html",
            ["foo.org/a/article/document.html"],
            False,
        ),
        (  # Full URL since not in known URLs
            "https://kiwix.org/a/article/document.html",
            "https://foo.org/a/article/document.html",
            "https://foo.org/a/article/document.html",
            ["kiwix.org/a/article/foo/"],
            False,
        ),
        (  # all URLs rewrite activated
            "https://kiwix.org/a/article/document.html",
            "https://foo.org/a/article/document.html",
            "../../../foo.org/a/article/document.html",
            ["kiwix.org/a/article/foo/"],
            True,
        ),
        (  # puny-encoded host is transformed into url-encoded value
            "https://kiwix.org/a/article/document.html",
            "https://xn--exmple-cva.com/a/article/document.html",
            "../../../ex%C3%A9mple.com/a/article/document.html",
            ["exémple.com/a/article/document.html"],
            False,
        ),
        (  # host who should be puny-encoded is transformed into url-encoded value
            "https://kiwix.org/a/article/document.html",
            "https://exémple.com/a/article/document.html",
            "../../../ex%C3%A9mple.com/a/article/document.html",
            ["exémple.com/a/article/document.html"],
            False,
        ),
    ],
)
def test_absolute_url(
    article_url,
    know_paths,
    original_content_url,
    expected_rewriten_content_url,
    rewrite_all_url,
):
    article_url = HttpUrl(article_url)
    rewriter = ArticleUrlRewriter(
        article_url,
        {ZimPath(path) for path in know_paths},
    )
    assert (
        rewriter(original_content_url, base_href=None, rewrite_all_url=rewrite_all_url)
        == expected_rewriten_content_url
    )


@pytest.mark.parametrize(
    "original_content_url, rewrite_all_url",
    [
        ("data:0548datacontent", False),
        ("blob:exemple.com/url", False),
        ("mailto:bob@acme.com", False),
        ("tel:+33.1.12.12.23", False),
        ("data:0548datacontent", True),
        ("blob:exemple.com/url", True),
        ("mailto:bob@acme.com", True),
        ("tel:+33.1.12.12.23", True),
    ],
)
# other schemes are never rewritten, even when rewrite_all_url is true
def test_no_rewrite_other_schemes(original_content_url, rewrite_all_url):
    article_url = HttpUrl("https://kiwix.org/a/article/document.html")
    rewriter = ArticleUrlRewriter(
        article_url,
        set(),
    )
    assert (
        rewriter(original_content_url, base_href=None, rewrite_all_url=rewrite_all_url)
        == original_content_url
    )


@pytest.mark.parametrize(
    "original_content_url, know_path, base_href, expected_rewriten_content_url",
    [
        pytest.param(
            "foo.html",
            "kiwix.org/a/article/foo.html",
            None,
            "foo.html",
            id="no_base",
        ),
        pytest.param(
            "foo.html",
            "kiwix.org/a/foo.html",
            "../",
            "../foo.html",
            id="parent_base",
        ),
        pytest.param(
            "foo.html",
            "kiwix.org/a/bar/foo.html",
            "../bar/",
            "../bar/foo.html",
            id="base_in_another_folder",
        ),
        pytest.param(
            "foo.html",
            "www.example.com/foo.html",
            "https://www.example.com/",
            "../../../www.example.com/foo.html",
            id="base_on_absolute_url",
        ),
    ],
)
def test_base_href(
    original_content_url,
    know_path,
    base_href,
    expected_rewriten_content_url,
):
    rewriter = ArticleUrlRewriter(
        HttpUrl("https://kiwix.org/a/article/document.html"),
        {ZimPath(path) for path in [know_path]},
    )
    assert (
        rewriter(original_content_url, base_href=base_href, rewrite_all_url=False)
        == expected_rewriten_content_url
    )
