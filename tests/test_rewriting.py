import io

import pytest
from jinja2 import Template
from warcio import StatusAndHeaders
from warcio.recordloader import ArcWarcRecord

from warc2zim.content_rewriting.generic import Rewriter
from warc2zim.url_rewriting import ZimPath


@pytest.fixture(scope="module")
def rewrite_generator():
    """A fixture which return a generator for a generic rewriter"""

    def generate_and_call(
        content: bytes = b"dummy", content_type: str = "text/html; charset=UTF-8"
    ):
        rec_headers = StatusAndHeaders(
            "WARC/1.1",
            headers=[("WARC-Target-URI", "http://www.example.com")],
        )
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
