#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

from __future__ import annotations

import re
from http import HTTPStatus

from bs4 import BeautifulSoup
from warcio.recordloader import ArcWarcRecord

from warc2zim.__about__ import __version__

ENCODING_RE = re.compile(
    r"(charset|encoding)=(?P<quote>['\"]?)(?P<encoding>[a-wA-Z0-9_\-]+)(?P=quote)",
    re.ASCII,
)

ENCODING_ALIASES = {}


def set_encoding_aliases(aliases: dict[str, str]):
    """Set the encoding aliases to use to decode"""
    ENCODING_ALIASES.clear()
    ENCODING_ALIASES.update(aliases)


def get_version():
    return __version__


def get_record_url(record) -> str:
    """Check if record has url converted from POST/PUT, and if so, use that
    otherwise return the target url"""
    if hasattr(record, "urlkey"):
        return record.urlkey
    return str(record.rec_headers["WARC-Target-URI"])


def get_status_code(record: ArcWarcRecord) -> HTTPStatus | int | None:
    """Get the HTTP status of a given ArcWarcRecord

    Returns HTTPStatus value or None if status code is not found / supported
    """
    if record.rec_type == "response":
        status_code = record.http_headers.get_statuscode()
    else:
        status_code = record.rec_headers.get_statuscode()

    if status_code is None or status_code.strip() == "":
        # null / missing http status found, ignore it
        return None

    status_code = int(status_code)

    try:
        status_code = HTTPStatus(status_code)
    except ValueError:
        # invalid http status found, ignore it (happens when bad http status is
        # returned, e.g 0, 306)
        return status_code

    return status_code


def can_process_status_code(status_code: HTTPStatus | int | None) -> bool:
    """Return a boolean indicating if this status code is a processable redirect"""
    return isinstance(status_code, HTTPStatus) and not (
        status_code.is_informational  # not supposed to exist in WARC files
        or status_code.is_client_error
        or status_code.is_server_error
        or (
            status_code.is_success
            and status_code
            not in [
                HTTPStatus.OK,
                HTTPStatus.CREATED,
                HTTPStatus.ACCEPTED,
                HTTPStatus.NON_AUTHORITATIVE_INFORMATION,
            ]
        )
        or (
            status_code.is_redirection
            and status_code
            not in [
                HTTPStatus.MOVED_PERMANENTLY,
                HTTPStatus.FOUND,
                HTTPStatus.TEMPORARY_REDIRECT,
                HTTPStatus.PERMANENT_REDIRECT,
            ]
        )
    )


def status_code_is_processable_redirect(status_code: HTTPStatus | int | None) -> bool:
    """Return a boolean indicating if this status code is processable redirect"""
    return isinstance(status_code, HTTPStatus) and status_code in [
        HTTPStatus.MOVED_PERMANENTLY,
        HTTPStatus.FOUND,
        HTTPStatus.TEMPORARY_REDIRECT,
        HTTPStatus.PERMANENT_REDIRECT,
    ]


def get_record_content_type(record: ArcWarcRecord) -> str:
    if record.http_headers:
        # if the record has HTTP headers, use the Content-Type from those
        # (eg. 'response' record)
        content_type = record.http_headers["Content-Type"]
    else:
        # otherwise, use the Content-Type from WARC headers
        content_type = record.rec_headers["Content-Type"]
    return content_type or ""


def get_record_mime_type(record: ArcWarcRecord) -> str:
    content_type = get_record_content_type(record)
    return content_type.split(";")[0]


def parse_title(content):
    try:
        soup = BeautifulSoup(content, "html.parser")
        return soup.title.text or ""  # pyright: ignore[reportOptionalMemberAccess]
    except Exception:
        return ""


def get_record_encoding(record: ArcWarcRecord) -> str | None:
    content_type = get_record_content_type(record)
    if m := ENCODING_RE.search(content_type):
        return m.group("encoding")


def to_string(
    input_: str | bytes,
    http_encoding: str | None,
    charsets_to_try: list[str],
    content_header_bytes_length: int,
    *,
    ignore_content_header_charsets: bool,
    ignore_http_header_charsets: bool,
) -> str:
    """
    Decode content to string based on charset declared in content or fallback.

    This method tries to not be smarter than necessary.

    First, it tries to find an charset declaration inside the first bytes of the content
    (hopping that content first bytes can be losely decoded using few known encoding to
    something usable). If found, it is used to decode and any bad character is
    automatically replaced, assuming document editor is right.

    Second, if no charset declaration has been found in content, it uses the charset
    declared in HTTP `Content-Type` header. This is passed to this method as
    `http_encoding` argument. If present, it is used to decode and any bad character is
    automatically replaced, assuming web server is right.

    Finally, we fallback to use `charsets_to_try` argument, which is a list of charsets
    to try. Each charset is tried in order, but any bad character found is raising an
    error. If none of these charsets achieves to decode the content, an exception is
    raised.

    Returns the decoded content.

    """

    if isinstance(input_, str):
        return input_

    if not input_:
        # Empty bytes are easy to decode
        return ""

    # Search for encoding from content first bytes based on regexp
    if not ignore_content_header_charsets:
        for encoding in ["ascii", "utf-16", "utf-32"]:
            content_start = input_[:content_header_bytes_length].decode(
                encoding, errors="replace"
            )
            if m := ENCODING_RE.search(content_start):
                head_encoding = m.group("encoding")
                return input_.decode(
                    ENCODING_ALIASES.get(head_encoding, head_encoding), errors="replace"
                )

    # Search for encofing in HTTP `Content-Type` header
    if not ignore_http_header_charsets and http_encoding:
        return input_.decode(
            ENCODING_ALIASES.get(http_encoding, http_encoding), errors="replace"
        )

    # Try all charsets_to_try passed
    for charset_to_try in charsets_to_try:
        try:
            return input_.decode(ENCODING_ALIASES.get(charset_to_try, charset_to_try))
        except (ValueError, LookupError):
            pass

    raise ValueError(f"No suitable charset found to decode content {input_[:200]}")


def get_record_content(record: ArcWarcRecord) -> bytes:
    if hasattr(record, "buffered_stream"):
        stream = (
            record.buffered_stream  # pyright: ignore [reportGeneralTypeIssues, reportAttributeAccessIssue]
        )
        stream.seek(0)
        return stream.read()
    else:
        return record.content_stream().read()
