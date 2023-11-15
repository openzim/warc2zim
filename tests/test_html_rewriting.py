import pytest
from warc2zim.content_rewriting import HtmlRewriter


@pytest.fixture(
    params=[
        "A simple string without url",
        "<html><body><p>This is a sentence with a http://exemple.com/path link</p></body></html>",
        '<a data-source="http://exemple.com/path">A link we should not rewrite</a>',
        '<p style="background: url(some/image.png)">A url (relative) in a inline style</p>',
        "<style>p { /* A comment with a http://link.org/ */ background: url('some/image.png') ; }</style>",
    ]
)
def no_rewrite_content(request):
    yield request.param


def test_no_rewrite(no_rewrite_content):
    assert (
        HtmlRewriter("kiwix.org").rewrite(no_rewrite_content).content
        == no_rewrite_content
    )


@pytest.fixture(
    params=[
        (
            "<p style='background: url(\"some/image.png\")'>A link in a inline style</p>",
            '<p style="background: url(&quot;some/image.png&quot;)">A link in a inline style</p>',
        ),
        (
            "<p style=\"background: url('some/image.png')\">A link in a inline style</p>",
            '<p style="background: url(&#x27;some/image.png&#x27;)">A link in a inline style</p>',
        ),
        ("<ul style='list-style: \">\"'>", '<ul style="list-style: &quot;&gt;&quot;">'),
    ]
)
def escaped_content(request):
    yield request.param


def test_escaped_content(escaped_content):
    (input_str, expected) = escaped_content
    transformed = HtmlRewriter("kiwix.org").rewrite(input_str).content
    assert transformed == expected


@pytest.fixture(
    params=[
        # Normalized path is "exemple.com/a/long/path"
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com",
            "exemple.com/a/long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "kiwix.org",
            "exemple.com/a/long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "kiwix.org/",
            "../exemple.com/a/long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/",
            "a/long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a",
            "a/long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/",
            "long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/long",
            "long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/long/",
            "path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/long/path",
            "path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/long/path/yes",
            ".",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "exemple.com/a/very/long/path",
            "../../long/path",
        ),
        (
            '<a href="http://exemple.com/a/long/path">A link to rewrite</a>',
            "kiwix.org/another/path",
            "../../exemple.com/a/long/path",
        ),
    ]
)
def rewrite_url(request):
    yield request.param


def test_rewrite(rewrite_url):
    (input_str, article_url, rewriten) = rewrite_url
    expected = input_str.replace("http://exemple.com/a/long/path", rewriten)
    assert HtmlRewriter(article_url).rewrite(input_str).content == expected


def test_extract_title():
    content = """<html>
      <head>
        <title>Page title</title>
      </head>
      <body>
        <title>Wrong page title</title>
      </body>
    </html>"""

    assert HtmlRewriter("kiwix.org").rewrite(content).title == "Page title"


def test_rewrite_attributes():
    rewriter = HtmlRewriter("kiwix.org/")

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
