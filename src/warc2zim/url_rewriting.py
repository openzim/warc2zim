#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim's url rewriting tools

This module is about url and entry path rewriting.

The global scheme is the following:

Entries are stored in the zim file using their urldecoded full path properly urlencoded (yes!):
- The full path is the full url without the scheme (ie : "<host>/<path>(?<query_string)")
  The scheme information is lost. We will serve the content using the scheme of the real server,
  whatever was the scheme of the original url.
  We probably don't care about different content served from different scheme but with same `host/path`.
- urldecoded: As most as possible the path itself must not be urlencoded:
  . This is valid : "foo/part with space/bar?key=value"
  . This is NOT valid : "foo/part%20with%20space/bar%3Fkey%3Dvalue"
- Properly urlencoded: However, for correct parsing, some character may still need to be encoded.
  The querystring components (and others) must be url encoded as needed:
  . This is valid : "foo/part/file with %3F and +?who=Chip%26Dale&question=Is%20there%20any%20%2B%20here%3F"
  . This is NOT valid : "foo/part/file with ? and +?who=Chip&Dale&question=It there any + here?"
- Space in query string must be encoded with `%20` not `+`:
  . This is valid : "foo/part/file?question=Is%20there%20any%20%2B%20here%3F"
  . This is NOT valid : "foo/part/file?question=Is+there+any+%2B+here%3F"

In python words :
- full path are `urllib.parse.ParseResults` with `scheme==''`
- `urllib.parse.urlparse` must correctly parse the path (generating `ParseResults` with empty scheme)
- The querystring part must be parsable by `urllib.parse.parse_qs` (even if we don't do it here)
- The querystring must be generated as by `urllib.parse.urlencode(<query>, quote_via=quote)`

On top of that, paths are "reduced" using fuzzy rules:
A path "https://www.youtube.com/youtubei/v1/foo/baz/things?key=value&other_key=other_value&videoId=xxxx&yet_another_key=yet_another_value"
is reduced to "youtube.fuzzy.replayweb.page/youtubei/v1/foo/baz/things?videoId=xxxx"
by slightly simplifying the path and keeping only the usefull arguments in the querystring.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit, urlunsplit, quote, unquote, parse_qs, urlencode
from warc2zim.utils import to_string

# Shared logger
logger = logging.getLogger("warc2zim.url_rewriting")


FUZZY_RULES = [
    {
        "match": re.compile(
            # r"//.*googlevideo.com/(videoplayback\?).*(id=[^&]+).*([&]itag=[^&]+).*"
            r".*googlevideo.com/(videoplayback\?).*((?<=[?&])id=[^&]+).*"
        ),
        "replace": r"youtube.fuzzy.replayweb.page/\1\2",
    },
    {
        "match": re.compile(
            r"(?:www\.)?youtube(?:-nocookie)?\.com/(get_video_info\?)"
            r".*(video_id=[^&]+).*"
        ),
        "replace": r"youtube.fuzzy.replayweb.page/\1\2",
    },
    {"match": re.compile(r"([^?]+\?)[\d]+$"), "replace": r"\1"},
    {
        "match": re.compile(
            r"(?:www\.)?youtube(?:-nocookie)?\.com\/(youtubei\/[^?]+).*(videoId[^&]+).*"
        ),
        "replace": r"youtube.fuzzy.replayweb.page/\1?\2",
    },
    {
        "match": re.compile(r"(?:www\.)?youtube(?:-nocookie)?\.com/embed/([^?]+).*"),
        "replace": r"youtube.fuzzy.replayweb.page/embed/\1",
    },
    {
        "match": re.compile(
            r".*(?:gcs-vimeo|vod|vod-progressive)\.akamaized\.net.*?/([\d/]+.mp4)$"
        ),
        "replace": r"vimeo-cdn.fuzzy.replayweb.page/\1",
    },
    {
        "match": re.compile(r".*player.vimeo.com/(video/[\d]+)\?.*"),
        "replace": r"vimeo.fuzzy.replayweb.page/\1",
    },
]


def reduce(path: str) -> str:
    """Reduce a path"""
    for rule in FUZZY_RULES:
        if match := rule["match"].match(path):
            return match.expand(rule["replace"])
    return path


def normalize(url: str | bytes) -> str:
    """Normalize a properly contructed url to a path to use as a entry's key.

    >>> normalize("http://exemple.com/path/to/article?foo=bar")
    "exemple.com/path/to/article?foo=bar"
    >>> normalize("http://other.com/path to strange ar+t%3Ficle?foo=bar+baz")
    "other.com/path to strange ar+t%3Ficle?foo=bar%20baz"
    >>> normalize("http://youtube.com/youtubei/bar?key=value&videoId=xxxx&otherKey=otherValue")
    "youtube.fuzzy.replayweb.page/youtubei/bar?videoId=xxxx"
    """

    if not url:
        return url

    url = to_string(url)

    url_parts = urlsplit(url)
    url_parts = url_parts._replace(scheme="")

    # Remove the netloc (by moving it into path)
    if url_parts.netloc:
        new_path = url_parts.netloc + url_parts.path
        url_parts = url_parts._replace(netloc="", path=new_path)
    if url_parts.path and url_parts.path[0] == "/":
        url_parts = url_parts._replace(path=url_parts.path[1:])

    path = urlunsplit(url_parts)
    path = reduce(path)

    return path
