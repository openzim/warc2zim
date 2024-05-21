#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

from __future__ import annotations

import re
from http import HTTPStatus
from typing import NamedTuple

import chardet
from bs4 import BeautifulSoup
from warcio.recordloader import ArcWarcRecord

from warc2zim.__about__ import __version__

ENCODING_RE = re.compile(
    r"(charset|encoding)=(?P<quote>['\"]?)(?P<encoding>[a-wA-Z0-9_\-]+)(?P=quote)",
    re.ASCII,
)


class StringConversionResult(NamedTuple):
    value: str
    encoding: str | None
    chars_ignored: bool


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


def to_string(input_: str | bytes, encoding: str | None) -> StringConversionResult:
    """
    Decode content to string, trying to be the more tolerant possible to invalid
    declared encoding.

    This try to decode the content using 3 methods:
     - From http headers in the warc record (given as `encoding` argument)
     - From encoding declaration inside the content (hopping that content can be
       losely decode using ascii to something usable)
     - From statistical analysis of the content (made by chardet)

    If all these methods fails, try again with the encoding passed via http headers but
    ignore all unrecognized characters.

    Returns the decoded content, the encoding used (or None if the input was already
    decoded) and a boolean indicating wether unrecognized characters had to been ignored
    or not.

    """
    http_encoding = encoding

    tried_encodings: set[str] = set()
    if isinstance(input_, str):
        return StringConversionResult(input_, None, False)

    if not input_:
        # Empty bytes are easy to decode
        return StringConversionResult("", None, False)

    if encoding:
        try:
            return StringConversionResult(input_.decode(encoding), encoding, False)
        except (ValueError, LookupError):
            tried_encodings.add(encoding)
            pass

    # Search for encoding from content first bytes based on regexp
    content_start = input_[:1024].decode("ascii", errors="replace")
    if m := ENCODING_RE.search(content_start):
        encoding = m.group("encoding")
        if encoding and encoding not in tried_encodings:
            try:
                return StringConversionResult(input_.decode(encoding), encoding, False)
            except (ValueError, LookupError):
                tried_encodings.add(encoding)
                pass

    # Try to detect the most probable encoding with chardet (and only most probable
    # one, since otherwise we will likely find an encoding which pass but produces only
    # garbage with most characters badly decoded just due to a wrongly encoded character
    # see https://github.com/openzim/warc2zim/issues/221)
    # Nota: we use the detect_all method of chardet even if we are interesting only in
    # the most probable encoding, because (as-of chardet 5.2.0 at least) the detect
    # chardet method seems to be more naive, and detect_all gives better results in our
    # tests
    chardet_encodings = chardet.detect_all(input_)
    if len(chardet_encodings):
        chardet_encoding = chardet_encodings[0]["encoding"]
        if chardet_encoding and chardet_encoding not in tried_encodings:
            try:
                return StringConversionResult(
                    input_.decode(chardet_encoding), chardet_encoding, False
                )
            except (ValueError, LookupError):
                tried_encodings.add(chardet_encoding)
                pass

    # Try again encoding detected by chardet (most probable one), but this time ignore
    # all bad chars
    if http_encoding:
        try:
            return StringConversionResult(
                input_.decode(http_encoding, errors="ignore"), http_encoding, True
            )
        except (ValueError, LookupError):
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
