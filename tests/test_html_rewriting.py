from textwrap import dedent

import pytest

from warc2zim.content_rewriting import HtmlRewriter
from .utils import TestContent


@pytest.fixture(
    params=[
        TestContent("A simple string without url"),
        TestContent(
            "<html><body><p>This is a sentence with a http://exemple.com/path link</p></body></html>"
        ),
        TestContent(
            '<a data-source="http://exemple.com/path">A link we should not rewrite</a>'
        ),
        TestContent(
            '<p style="background: url(some/image.png);">A url (relative) in a inline style</p>'
        ),
        TestContent(
            '<style>p { /* A comment with a http://link.org/ */ background: url("some/image.png") ; }</style>'
        ),
    ]
)
def no_rewrite_content(request):
    yield request.param


def test_no_rewrite(no_rewrite_content):
    assert (
        HtmlRewriter(no_rewrite_content.article_url, "", "")
        .rewrite(no_rewrite_content.input)
        .content
        == no_rewrite_content.expected
    )


@pytest.fixture(
    params=[
        TestContent(
            "<p style='background: url(\"some/image.png\")'>A link in a inline style</p>",
            '<p style="background: url(&quot;some/image.png&quot;);">A link in a inline style</p>',
        ),
        TestContent(
            "<p style=\"background: url('some/image.png')\">A link in a inline style</p>",
            '<p style="background: url(&quot;some/image.png&quot;);">A link in a inline style</p>',
        ),
        TestContent(
            "<ul style='list-style: \">\"'>",
            '<ul style="list-style: &quot;&gt;&quot;;">',
        ),
    ]
)
def escaped_content(request):
    yield request.param


def test_escaped_content(escaped_content):
    transformed = (
        HtmlRewriter(escaped_content.article_url, "", "")
        .rewrite(escaped_content.input)
        .content
    )
    assert transformed == escaped_content.expected


def long_path_replace_test_content(input: str, rewriten_url: str, article_url: str):
    expected = input.replace("http://exemple.com/a/long/path", rewriten_url)
    return TestContent(input, expected, article_url)


lprtc = long_path_replace_test_content


@pytest.fixture(
    params=[
        # Normalized path is "exemple.com/a/long/path"
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/long/path",
            "exemple.com",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/long/path",
            "kiwix.org",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../exemple.com/a/long/path",
            "kiwix.org/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "a/long/path",
            "exemple.com/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "a/long/path",
            "exemple.com/a",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "long/path",
            "exemple.com/a/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "long/path",
            "exemple.com/a/long",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "path",
            "exemple.com/a/long/",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "path",
            "exemple.com/a/long/path",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            ".",
            "exemple.com/a/long/path/yes",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../../long/path",
            "exemple.com/a/very/long/path",
        ),
        lprtc(
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "../../exemple.com/a/long/path",
            "kiwix.org/another/path",
        ),
    ]
)
def rewrite_url(request):
    yield request.param


def test_rewrite(rewrite_url):
    assert (
        HtmlRewriter(rewrite_url.article_url, "", "").rewrite(rewrite_url.input).content
        == rewrite_url.expected
    )


def test_extract_title():
    content = """<html>
      <head>
        <title>Page title</title>
      </head>
      <body>
        <title>Wrong page title</title>
      </body>
    </html>"""

    assert HtmlRewriter("kiwix.org", "", "").rewrite(content).title == "Page title"


def test_rewrite_attributes():
    rewriter = HtmlRewriter("kiwix.org/", "", "")

    assert (
        rewriter.rewrite("<a href='https://kiwix.org/foo'>A link</a>").content
        == '<a href="foo">A link</a>'
    )

    assert (
        rewriter.rewrite("<img src='https://kiwix.org/foo'></img>").content
        == '<img src="foo"></img>'
    )

    assert (
        rewriter.rewrite(
            "<img srcset='https://kiwix.org/img-480w.jpg 480w, https://kiwix.org/img-800w.jpg 800w'></img>"
        ).content
        == '<img srcset="img-480w.jpg 480w, img-800w.jpg 800w"></img>'
    )


def test_rewrite_css():
    output = (
        HtmlRewriter("", "", "")
        .rewrite(
            "<style>p { /* A comment with a http://link.org/ */ background: url('some/image.png') ; }</style>",
        )
        .content
    )
    assert (
        output
        == '<style>p { /* A comment with a http://link.org/ */ background: url("some/image.png") ; }</style>'
    )


def test_head_insert():
    content = """<html>
    <head>
        <title>A test content</title>
    </head>
    <body></body>
    </html>"""

    content = dedent(content)

    assert HtmlRewriter("foo", "", "").rewrite(content).content == content

    assert HtmlRewriter("foo", "PRE_HEAD_INSERT", "").rewrite(
        content
    ).content == content.replace("<head>", "<head>PRE_HEAD_INSERT")
    assert HtmlRewriter("foo", "", "POST_HEAD_INSERT").rewrite(
        content
    ).content == content.replace("</head>", "POST_HEAD_INSERT</head>")
    assert HtmlRewriter("foo", "PRE_HEAD_INSERT", "POST_HEAD_INSERT").rewrite(
        content
    ).content == content.replace("<head>", "<head>PRE_HEAD_INSERT").replace(
        "</head>", "POST_HEAD_INSERT</head>"
    )
