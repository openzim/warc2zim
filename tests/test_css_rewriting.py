import pytest
from warc2zim.url_rewriting import ArticleUrlRewriter
from warc2zim.content_rewriting import CssRewriter
from textwrap import dedent


@pytest.fixture(
    params=[
        b"p { color: red; }",
        b"p {\n color: red;\n}",
        b"p { background: blue; }",
        b"p { background: rgb(15, 0, 52); }",
        b"/* See bug issue at http://exemple.com/issue/link */ p { color: blue; }",
    ]
)
def no_rewrite_content(request):
    yield request.param


def test_no_rewrite(no_rewrite_content):
    assert (
        CssRewriter(ArticleUrlRewriter("kiwix.org", set())).rewrite(no_rewrite_content)
        == no_rewrite_content.decode()
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
    src: url(https://fonts.gstatic.com/s/quicksand/v31/6xKtdSZaM9iE8KbpRA_hJFQNcOM.woff2) format('woff2');
}

@media only screen and (max-width: 40em) {
    p, input {
        background-image:url(data:image/png;base64,FooContent);
    }
}"""

    expected = """
    /* A comment with a link : http://foo.com */
    @import url(../fonts.googleapis.com/icon%3Ffamily%3DMaterial%2BIcons);

    p, input {
        color: rbg(1, 2, 3);
        background: url("super/img");
        background-image:url("../exemple.com/no_space_before_url");
    }

    @font-face {
        src: url(../fonts.gstatic.com/s/quicksand/v31/6xKtdSZaM9iE8KbpRA_hJFQNcOM.woff2) format("woff2");
    }

    @media only screen and (max-width: 40em) {
        p, input {
            background-image:url(data:image/png;base64,FooContent);
        }
    }"""
    expected = dedent(expected)

    assert (
        CssRewriter(ArticleUrlRewriter("kiwix.org/article", set())).rewrite(content)
        == expected
    )
