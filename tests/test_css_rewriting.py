from textwrap import dedent

import pytest

from warc2zim.content_rewriting.css import CssRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl

from .utils import ContentForTests


@pytest.fixture(
    params=[
        ContentForTests(b"p { color: red; }"),
        ContentForTests(b"p {\n color: red;\n}"),
        ContentForTests(b"p { background: blue; }"),
        ContentForTests(b"p { background: rgb(15, 0, 52); }"),
        ContentForTests(
            b"/* See bug issue at http://exemple.com/issue/link */ p { color: blue; }"
        ),
        ContentForTests(
            b"p { width= } div { background: url(http://exemple.com/img.png)}",
            b"p { width= } div { background: url(../exemple.com/img.png)}",
        ),
        ContentForTests(
            b"p { width= } div { background: url('http://exemple.com/img.png')}",
            b'p { width= } div { background: url("../exemple.com/img.png")}',
        ),
        ContentForTests(
            b'p { width= } div { background: url("http://exemple.com/img.png")}',
            b'p { width= } div { background: url("../exemple.com/img.png")}',
        ),
    ]
)
def no_rewrite_content(request):
    yield request.param


def test_no_rewrite(no_rewrite_content):
    assert (
        CssRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{no_rewrite_content.article_url}"), set()
            ),
            base_href=None,
        ).rewrite(no_rewrite_content.input_bytes)
        == no_rewrite_content.expected_bytes.decode()
    )


@pytest.fixture(
    params=[
        ContentForTests('"border:'),
        ContentForTests("border: solid 1px #c0c0c0; width= 100%"),
        # Despite being invalid, tinycss parse it as "width" property without value.
        ContentForTests("width:", "width:;"),
        ContentForTests("border-bottom-width: 1px;border-bottom-color: #c0c0c0;w"),
        ContentForTests(
            'background: url("http://exemple.com/foo.png"); width=',
            'background: url("../exemple.com/foo.png"); width=',
        ),
    ]
)
def invalid_content_inline(request):
    yield request.param


def test_invalid_css_inline(invalid_content_inline):
    assert (
        CssRewriter(
            ArticleUrlRewriter(
                HttpUrl(f"http://{invalid_content_inline.article_url}"), set()
            ),
            base_href=None,
        ).rewrite_inline(invalid_content_inline.input_str)
        == invalid_content_inline.expected_str
    )


@pytest.fixture(
    params=[
        # Tinycss parse `"border:}` as a string with an unexpected eof in string.
        # At serialization, tiny try to recover and close the opened rule
        ContentForTests(b'p {"border:}', b'p {"border:}}'),
        ContentForTests(b'"p {border:}'),
        ContentForTests(b"p { border: solid 1px #c0c0c0; width= 100% }"),
        ContentForTests(b"p { width: }"),
        ContentForTests(
            b"p { border-bottom-width: 1px;border-bottom-color: #c0c0c0;w }"
        ),
        ContentForTests(
            b'p { background: url("http://exemple.com/foo.png"); width= }',
            b'p { background: url("../exemple.com/foo.png"); width= }',
        ),
    ]
)
def invalid_content(request):
    yield request.param


def test_invalid_cssl(invalid_content):
    assert (
        CssRewriter(
            ArticleUrlRewriter(HttpUrl(f"http://{invalid_content.article_url}"), set()),
            base_href=None,
        ).rewrite(invalid_content.input_bytes)
        == invalid_content.expected_bytes.decode()
    )


def test_rewrite():
    content = b"""
/* A comment with a link : http://foo.com */
@import url(//fonts.googleapis.com/icon?family=Material+Icons);

p, input {
    color: rbg(1, 2, 3);
    background: url('http://kiwix.org/super/img');
    background-image:url('http://exemple.com/no_space_before_url');
}

@font-face {
    src: url(https://f.gst.com/s/qa/v31/6xKtdSZaE8KbpRA_hJFQNcOM.woff2) format('woff2');
}

@media only screen and (max-width: 40em) {
    p, input {
        background-image:url(data:image/png;base64,FooContent);
    }
}"""

    expected = """
    /* A comment with a link : http://foo.com */
    @import url(../fonts.googleapis.com/icon%3Ffamily%3DMaterial%20Icons);

    p, input {
        color: rbg(1, 2, 3);
        background: url("super/img");
        background-image:url("../exemple.com/no_space_before_url");
    }

    @font-face {
        src: url(../f.gst.com/s/qa/v31/6xKtdSZaE8KbpRA_hJFQNcOM.woff2) format("woff2");
    }

    @media only screen and (max-width: 40em) {
        p, input {
            background-image:url(data:image/png;base64,FooContent);
        }
    }"""
    expected = dedent(expected)

    assert (
        CssRewriter(
            ArticleUrlRewriter(HttpUrl("http://kiwix.org/article"), set()),
            base_href=None,
        ).rewrite(content)
        == expected
    )
