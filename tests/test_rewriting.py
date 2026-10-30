import io

import pytest
from jinja2 import Template
from warcio import StatusAndHeaders
from warcio.recordloader import ArcWarcRecord
from zimscraperlib.rewriting.url_rewriting import ZimPath

from warc2zim.rewriting import Rewriter, extract_jsonp_callback


@pytest.fixture(scope="module")
def rewrite_generator():
    """A fixture which return a generator for a generic rewriter"""

    def generate_and_call(
        content: bytes = b"dummy",
        content_type: str = "text/html; charset=UTF-8",
        url: str = "http://www.example.com",
        resource_type: str | None = None,
    ):
        headers = [("WARC-Target-URI", url)]
        if resource_type:
            headers.append(("WARC-Resource-Type", resource_type))
        rec_headers = StatusAndHeaders("WARC/1.1", headers=headers)
        http_headers = StatusAndHeaders(
            "HTTP/1.1 200 OK",
            headers=[("Content-Type", content_type)],
        )
        return Rewriter(
            ZimPath("www.example.com"),
            ArcWarcRecord(
                "warc",  # format = warc
                "response",  # rec_type = response
                rec_headers,
                io.BytesIO(content),
                http_headers,
                "application/http; msgtype=response",
                content.__len__(),
            ),
            set(),
            set(),
            set(),
            ["UTF-8", "ISO-8859-1"],
            1024,
            ignore_http_header_charsets=False,
            ignore_content_header_charsets=False,
        ).rewrite(Template(""), Template(""))

    yield generate_and_call


@pytest.mark.parametrize(
    "content_str, encoding, content_type",
    [
        pytest.param("Bérénice", "UTF-8", "text/html", id="html_content_utf8_auto"),
        pytest.param("Bérénice", "UTF-8", "text/css", id="js_content_utf8_auto"),
        pytest.param(
            "Bérénice", "UTF-8", "text/javascript", id="css_content_utf8_auto"
        ),
        pytest.param(
            "Bérénice", "UTF-8", "youdontknowme", id="unknown_content_utf8_auto"
        ),
        pytest.param("Bérénice", "ISO-8859-1", "text/html", id="html_content_iso_auto"),
        pytest.param("Bérénice", "ISO-8859-1", "text/css", id="js_content_iso_auto"),
        pytest.param(
            "Bérénice", "ISO-8859-1", "text/javascript", id="css_content_iso_auto"
        ),
        pytest.param(
            "Bérénice", "ISO-8859-1", "youdontknowme", id="unknown_content_iso_auto"
        ),
        pytest.param(
            "Bérénice",
            "UTF-8",
            "text/html; charset=UTF-8",
            id="html_content_utf8_declared",
        ),
        pytest.param(
            "Bérénice",
            "UTF-8",
            "text/css; charset=UTF-8",
            id="js_content_utf8_declared",
        ),
        pytest.param(
            "Bérénice",
            "UTF-8",
            "text/javascript; charset=UTF-8",
            id="css_content_utf8_declared",
        ),
        pytest.param(
            "Bérénice",
            "UTF-8",
            "youdontknowme; charset=UTF-8",
            id="unknown_content_utf8_declared",
        ),
        pytest.param(
            "Bérénice",
            "ISO-8859-1",
            "text/html; charset=ISO-8859-1",
            id="html_content_iso_declared",
        ),
        pytest.param(
            "Bérénice",
            "ISO-8859-1",
            "text/css; charset=ISO-8859-1",
            id="js_content_iso_declared",
        ),
        pytest.param(
            "Bérénice",
            "ISO-8859-1",
            "text/javascript; charset=ISO-8859-1",
            id="css_content_iso_declared",
        ),
        pytest.param(
            "Bérénice",
            "ISO-8859-1",
            "youdontknowme; charset=ISO-8859-1",
            id="unknown_content_iso_declared",
        ),
    ],
)
def test_generic_rewriting_encoding_handling(
    rewrite_generator, content_str, encoding, content_type
):
    """Test handling of encoding in various content types"""
    content_bytes = content_str.encode(encoding)
    (_, content) = rewrite_generator(content=content_bytes, content_type=content_type)
    if isinstance(content, bytes):
        # we return original bytes if content is not rewriten
        assert content == content_bytes
    else:
        assert content == content_str


def test_poster_attribute_rewriting(rewrite_generator):
    """Test that the poster attribute on video elements is properly rewritten."""
    content = (
        b"<!DOCTYPE html><html><body>"
        b'<video id="v1" controls poster="http://www.example.com/images/poster1.jpg">'
        b'<source src="http://www.example.com/videos/sample1.mp4" type="video/mp4">'
        b"</video>"
        b'<video id="v2" controls poster="./images/poster2.jpg">'
        b'<source src="./videos/sample2.mp4" type="video/mp4">'
        b"</video>"
        b"</body></html>"
    )
    _, rewritten = rewrite_generator(content=content, content_type="text/html")
    assert 'poster="images/poster1.jpg"' in rewritten
    assert "http://www.example.com/images/poster1.jpg" not in rewritten
    assert 'poster="images/poster2.jpg"' in rewritten
    assert 'poster="./images/poster2.jpg"' not in rewritten


@pytest.mark.parametrize(
    "content_type",
    [
        pytest.param("text/html", id="html"),
        pytest.param("application/xhtml+xml", id="xhtml_plus_xml"),
        pytest.param("application/xhtml+xml; charset=UTF-8", id="xhtml_with_charset"),
        pytest.param("application/xhtml", id="xhtml"),
    ],
)
@pytest.mark.parametrize("resource_type", [None, "document", "xhr", "fetch"])
def test_xhtml_rewritten_like_html(rewrite_generator, content_type, resource_type):
    content = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>My title</title>'
        b"</head><body>"
        b'<img src="http://www.example.com/images/image1.jpg" />'
        b"</body></html>"
    )
    title, rewritten = rewrite_generator(
        content=content, content_type=content_type, resource_type=resource_type
    )
    assert title == "My title"
    assert ' src="images/image1.jpg"' in rewritten
    assert ' src="http://www.example.com/images/image1.jpg"' not in rewritten


@pytest.mark.parametrize(
    "url, expected",
    [
        pytest.param(
            "https://api.example.com/data?callback=cb", "cb", id="callback_param"
        ),
        pytest.param("https://api.example.com/data?jsonp=cb", "cb", id="jsonp_param"),
        pytest.param(
            "https://api.example.com/data?CALLBACK=cb", "cb", id="case_insensitive"
        ),
        pytest.param(
            "https://api.example.com/data?callback=jQuery123_456&_=1700000000000",
            "jQuery123_456",
            id="followed_by_other_params",
        ),
        pytest.param(
            "https://api.example.com/data?q=test&callback=cb",
            "cb",
            id="preceded_by_other_params",
        ),
        pytest.param(
            "https://api.example.com/data?callback=Foo.bar", "Foo.bar", id="dotted_name"
        ),
        pytest.param("?callback=cb", "cb", id="query_string_only"),
        pytest.param("https://api.example.com/data", None, id="no_query_string"),
        pytest.param("https://api.example.com/data?q=test", None, id="no_callback"),
        pytest.param(
            "https://api.example.com/data?callback=?",
            None,
            id="jquery_placeholder_not_replaced",
        ),
        pytest.param("https://api.example.com/callback=cb", None, id="not_in_query"),
    ],
)
def test_extract_jsonp_callback(url, expected):
    assert extract_jsonp_callback(url) == expected


@pytest.mark.parametrize(
    "content, expected",
    [
        pytest.param(
            b'jQuery999_111({"a": 1});',
            'jQuery123_456({"a": 1});',
            id="object_payload",
        ),
        pytest.param(
            b"jQuery999_111([1, 2, 3]);",
            "jQuery123_456([1, 2, 3]);",
            id="array_payload",
        ),
        pytest.param(
            b'old.name({"a": 1})',
            'jQuery123_456({"a": 1})',
            id="dotted_recorded_name",
        ),
        pytest.param(
            b'jQuery999_111({"a": 1})',
            'jQuery123_456({"a": 1})',
            id="no_trailing_semicolon",
        ),
        pytest.param(
            b'  \n/* comment */\njQuery999_111({"a": 1});',
            '  \n/* comment */\njQuery123_456({"a": 1});',
            id="leading_whitespace_and_comment_kept",
        ),
        pytest.param(
            b'// comment\njQuery999_111({"a": 1});',
            '// comment\njQuery123_456({"a": 1});',
            id="leading_line_comment_kept",
        ),
        pytest.param(
            b'jQuery999_111({"a": 1}); other({"b": 2});',
            'jQuery123_456({"a": 1}); other({"b": 2});',
            id="only_leading_callback_replaced",
        ),
        pytest.param(
            b'jQuery999_111({"callback": "jQuery999_111"});',
            'jQuery123_456({"callback": "jQuery999_111"});',
            id="payload_not_touched",
        ),
        pytest.param(
            'jQuery999_111({"name": "Bérénice"});'.encode(),
            'jQuery123_456({"name": "Bérénice"});',
            id="non_ascii_payload",
        ),
    ],
)
@pytest.mark.parametrize(
    "content_type",
    [
        pytest.param("text/javascript", id="text_javascript"),
        pytest.param("application/javascript", id="application_javascript"),
        pytest.param("application/x-javascript", id="application_x_javascript"),
        pytest.param("text/javascript; charset=UTF-8", id="declared_charset"),
    ],
)
@pytest.mark.parametrize(
    "resource_type",
    [
        pytest.param(None, id="no_resource_type"),
        pytest.param("script", id="script_resource_type"),
        pytest.param("other", id="other_resource_type"),
    ],
)
def test_jsonp_rewriting(
    rewrite_generator, content, expected, content_type, resource_type
):
    _, rewritten = rewrite_generator(
        content=content,
        content_type=content_type,
        url="https://api.example.com/data?callback=jQuery123_456&_=1700000000000",
        resource_type=resource_type,
    )
    assert rewritten == expected


def test_jsonp_without_callback_in_url_is_not_rewritten_as_jsonp(rewrite_generator):
    content = b'jQuery999_111({"a": 1});'
    _, rewritten = rewrite_generator(
        content=content,
        content_type="text/javascript",
        url="https://api.example.com/data?q=test",
    )
    assert "jQuery999_111" in rewritten
    assert '({"a": 1})' in rewritten


def test_jsonp_callback_in_url_but_not_jsonp_content(rewrite_generator):
    content = b"function initMap() { console.log(window.location.href); }"
    _, rewritten = rewrite_generator(
        content=content,
        content_type="text/javascript",
        url="https://maps.example.com/api.js?callback=initMap",
    )
    assert rewritten != content.decode()
    assert "initMap" in rewritten
    assert "_____WB$wombat$" in rewritten
