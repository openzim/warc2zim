#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

from __future__ import annotations

import re
from http import HTTPStatus

import chardet
from bs4 import BeautifulSoup
from warcio.recordloader import ArcWarcRecord

from warc2zim.__about__ import __version__

ENCODING_RE = re.compile(
    r"(charset|encoding)=(?P<quote>['\"]?)(?P<encoding>[a-wA-Z0-9_\-]+)(?P=quote)",
    re.ASCII,
)


def get_version():
    return __version__


def get_record_url(record):
    """Check if record has url converted from POST/PUT, and if so, use that
    otherwise return the target url"""
    if hasattr(record, "urlkey"):
        return record.urlkey
    return record.rec_headers["WARC-Target-URI"]


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


def to_string(input_: str | bytes, encoding: str | None) -> str:
    """
    Decode content to string, trying to be the more tolerant possible to invalid
    declared encoding.

    This try decode the content using 3 methods:
     - From http headers in the warc record (given as `encoding` argument)
     - From encoding declaration inside the content (hopping that content can be
       losely decode using ascii to something usable)
     - From statistical analysis of the content (made by chardet)

    """
    tried_encodings = set()
    if isinstance(input_, str):
        return input_

    if not input_:
        # Empty bytes are easy to decode
        return ""

    if encoding:
        try:
            return input_.decode(encoding)
        except (ValueError, LookupError):
            tried_encodings.add(encoding)
            pass

    # Detect encoding from content.
    content_start = input_[:1024].decode("ascii", errors="replace")
    if m := ENCODING_RE.search(content_start):
        encoding = m.group("encoding")
        if encoding and encoding not in tried_encodings:
            try:
                return input_.decode(encoding)
            except (ValueError, LookupError):
                tried_encodings.add(encoding)
                pass

    encodings = (
        encoding
        for e in chardet.detect_all(input_)
        if (encoding := e["encoding"]) and encoding not in tried_encodings
    )

    for encoding in encodings:
        try:
            return input_.decode(encoding)
        except ValueError:
            pass
    raise ValueError(f"Impossible to decode content {input_[:200]}")


def get_record_content(record: ArcWarcRecord):
    if hasattr(record, "buffered_stream"):
        stream = (
            record.buffered_stream  # pyright: ignore [reportGeneralTypeIssues, reportAttributeAccessIssue]
        )
        stream.seek(0)
        return stream.read()
    else:
        return record.content_stream().read()
