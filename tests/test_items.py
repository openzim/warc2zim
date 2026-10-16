import io

from jinja2 import Template
from warcio import StatusAndHeaders
from warcio.recordloader import ArcWarcRecord
from zimscraperlib.rewriting.url_rewriting import ZimPath

from warc2zim.items import WARCPayloadItem
from warc2zim.rewriting import Rewriter


def make_record(content: bytes = b"dummy") -> ArcWarcRecord:
    rec_headers = StatusAndHeaders(
        "WARC/1.1",
        headers=[("WARC-Target-URI", "http://www.example.com")],
    )
    http_headers = StatusAndHeaders(
        "HTTP/1.1 200 OK",
        headers=[("Content-Type", "text/html; charset=UTF-8")],
    )
    return ArcWarcRecord(
        "warc",
        "response",
        rec_headers,
        io.BytesIO(content),
        http_headers,
        "application/http; msgtype=response",
        content.__len__(),
    )


def test_warc_payload_item_removes_unicode_surrogates(monkeypatch):
    """Content/title with surrogates must be sanitized before libzim"""

    monkeypatch.setattr(
        Rewriter,
        "rewrite",
        lambda self, *args, **kwargs: (  # noqa: ARG005
            "a title with a surrogate \udbff",
            "some content with a surrogate \udbff in it",
        ),
    )

    item = WARCPayloadItem(
        ZimPath("www.example.com"),
        make_record(),
        Template(""),
        Template(""),
        set(),
        set(),
        set(),
        ["UTF-8"],
        1024,
        ignore_content_header_charsets=False,
        ignore_http_header_charsets=False,
    )

    assert item.title == "a title with a surrogate �"
    assert item.content == "some content with a surrogate � in it"
