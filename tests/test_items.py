import io

import pymupdf
import pytest
from jinja2 import Template
from libzim.writer import Hint  # pyright: ignore[reportMissingModuleSource]
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
        pre_head_template=Template(""),
        post_head_template=Template(""),
        existing_zim_paths=set(),
        missing_zim_paths=set(),
        js_modules=set(),
        charsets_to_try=["UTF-8"],
        content_header_bytes_length=1024,
        ignore_content_header_charsets=False,
        ignore_http_header_charsets=False,
    )

    assert item.title == "a title with a surrogate �"
    assert item.content == "some content with a surrogate � in it"


def make_item(
    content: bytes, content_type: str, url: str = "http://www.example.com/page"
) -> WARCPayloadItem:
    rec_headers = StatusAndHeaders(
        "WARC/1.1",
        headers=[("WARC-Target-URI", url)],
    )
    http_headers = StatusAndHeaders(
        "HTTP/1.1 200 OK",
        headers=[("Content-Type", content_type)],
    )
    record = ArcWarcRecord(
        "warc",
        "response",
        rec_headers,
        io.BytesIO(content),
        http_headers,
        "application/http; msgtype=response",
        len(content),
    )
    return WARCPayloadItem(
        ZimPath("www.example.com/page"),
        record,
        pre_head_template=Template(""),
        post_head_template=Template(""),
        existing_zim_paths=set(),
        missing_zim_paths=set(),
        js_modules=set(),
        charsets_to_try=["UTF-8", "ISO-8859-1"],
        content_header_bytes_length=1024,
        ignore_http_header_charsets=False,
        ignore_content_header_charsets=False,
    )


def make_pdf_bytes(title: str | None) -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    if title:
        doc.set_metadata({"title": title})
    return doc.tobytes()


def test_html_with_title_is_front_article():
    item = make_item(
        b"<html><head><title>Hello</title></head><body>hi</body></html>",
        "text/html",
    )
    assert item.get_title() == "Hello"
    assert item.get_hints()[Hint.FRONT_ARTICLE] is True


def test_html_without_title_is_not_front_article():
    item = make_item(
        b"<html><head></head><body>no title tag here</body></html>",
        "text/html",
    )
    assert item.get_title() == ""
    assert item.get_hints()[Hint.FRONT_ARTICLE] is False


@pytest.mark.parametrize(
    "title, expect_front",
    [
        pytest.param("My Great PDF", True, id="with_metadata_title"),
        pytest.param(None, False, id="without_metadata_title"),
    ],
)
def test_pdf_title_from_metadata(title: str | None, *, expect_front: bool):
    item = make_item(make_pdf_bytes(title=title), "application/pdf")
    assert item.get_title() == (title or "")
    assert item.get_hints()[Hint.FRONT_ARTICLE] is expect_front


def test_non_front_mimetype_is_never_front_article():
    item = make_item(b"console.log('hello');", "application/javascript")
    assert item.get_hints()[Hint.FRONT_ARTICLE] is False
