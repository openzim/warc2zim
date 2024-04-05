#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim's url rewriting tools

This module is about url and entry path rewriting.

The global scheme is the following:

Entries are stored in the ZIM file using their decoded fully decoded path:
- The full path is the full url without the scheme, username, password, port, fragment
 (ie : "<host>/<path>(?<query_string)"). See documentation of the `normalize` function
 for more details.
- urldecoded: the path itself must not be urlencoded or it would conflict with ZIM
  specification and readers won't be able to retrieve it, some parts (e.g. querystring)
  might be absorbed by a web server, ...
  . This is valid : "foo/part with space/bar?key=value"
  . This is NOT valid : "foo/part%20with%20space/bar%3Fkey%3Dvalue"
- even having multiple ? in a ZIM path is valid
  . This is valid :
    "foo/part/file with ? and +?who=Chip&Dale&question=It there any + here?"
  . This is NOT valid :
    "foo/part/file with %3F and +?who=Chip%26Dale&quer=Is%20there%20any%20%2B%20here%3F"
- space in query string must be stored as ` `, not `%2B`, `%20` or `+`, the `+` in a ZIM
  path means a `%2B in web resource (HTML document, ...):
  . This is valid : "foo/part/file?question=Is there any + here?"
  . This is NOT valid : "foo/part/file?question%3DIs%20there%20any%20%2B%20here%3F"

On top of that, fuzzy rules are applied on the ZIM path:
For instance a path "https://www.youtube.com/youtubei/v1/foo/baz/things?key=value
&other_key=other_value&videoId=xxxx&yet_another_key=yet_another_value"
is transformed to "youtube.fuzzy.replayweb.page/youtubei/v1/foo/baz/things?videoId=xxxx"
by slightly simplifying the path and keeping only the usefull arguments in the
querystring.

When rewriting documents (HTML, CSS, JS, ...), every time we find a URI to rewrite we
start by resolving it into an absolute URL (based on the containing document absolute
URI), applying the transformation to compute the corresponding ZIM path and we
url-encode the whole ZIM path, so that readers will have one single blob to process,
url-decode and find corresponding ZIM entry. Only '/' separators are considered safe
and not url-encoded.
"""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from urllib.parse import (
    quote,
    unquote,
    urljoin,
    urlsplit,
    urlunsplit,
)

import idna

# Shared logger
logger = logging.getLogger("warc2zim.url_rewriting")

known_bad_hostnames: set[str] = set()

FUZZY_RULES = [
    {
        "pattern": r".*googlevideo.com/(videoplayback(?=\?)).*[?&](id=[^&]+).*",
        "replace": r"youtube.fuzzy.replayweb.page/\1?\2",
    },
    {
        "pattern": r"(?:www\.)?youtube(?:-nocookie)?\.com/(get_video_info\?).*(video_id"
        r"=[^&]+).*",
        "replace": r"youtube.fuzzy.replayweb.page/\1\2",
    },
    {"pattern": r"([^?]+)\?[\d]+$", "replace": r"\1"},
    {
        "pattern": r"(?:www\.)?youtube(?:-nocookie)?\.com\/(youtubei\/[^?]+).*(videoId["
        r"^&]+).*",
        "replace": r"youtube.fuzzy.replayweb.page/\1?\2",
    },
    {
        "pattern": r"(?:www\.)?youtube(?:-nocookie)?\.com/embed/([^?]+).*",
        "replace": r"youtube.fuzzy.replayweb.page/embed/\1",
    },
    {
        "pattern": r".*(?:gcs-vimeo|vod|vod-progressive)\.akamaized\.net.*?/([\d/]+"
        r".mp4)$",
        "replace": r"vimeo-cdn.fuzzy.replayweb.page/\1",
    },
    {
        "pattern": r".*player.vimeo.com/(video/[\d]+)\?.*",
        "replace": r"vimeo.fuzzy.replayweb.page/\1",
    },
]


COMPILED_FUZZY_RULES = [
    {"match": re.compile(rule["pattern"]), "replace": rule["replace"]}
    for rule in FUZZY_RULES
]


class HttpUrl:
    """A utility class representing an HTTP url, usefull to pass this data around

    Includes a basic validation, ensuring that URL is encoded, scheme is provided.
    """

    def __init__(self, value: str) -> None:
        HttpUrl.check_validity(value)
        self._value = value

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, HttpUrl) and __value.value == self.value

    def __hash__(self) -> int:
        return self.value.__hash__()

    def __str__(self) -> str:
        return f"HttpUrl({self.value})"

    @property
    def value(self) -> str:
        return self._value

    @classmethod
    def check_validity(cls, value: str) -> None:
        parts = urlsplit(value)

        if parts.scheme.lower() not in ["http", "https"]:
            raise ValueError(
                f"Incorrect HttpUrl scheme in value: {value} {parts.scheme}"
            )

        if not parts.hostname:
            raise ValueError(f"Unsupported empty hostname in value: {value}")

        if parts.hostname.lower() != parts.hostname:
            raise ValueError(f"Unsupported upper-case chars in hostname : {value}")


class ZimPath:
    """A utility class representing a ZIM path, usefull to pass this data around

    Includes a basic validation, ensuring that path does start with scheme, hostname,...
    """

    def __init__(self, value: str) -> None:
        ZimPath.check_validity(value)
        self._value = value

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, ZimPath) and __value.value == self.value

    def __hash__(self) -> int:
        return self.value.__hash__()

    def __str__(self) -> str:
        return f"ZimPath({self.value})"

    @property
    def value(self) -> str:
        return self._value

    @classmethod
    def check_validity(cls, value: str) -> None:
        parts = urlsplit(value)

        if parts.scheme:
            raise ValueError(f"Unexpected scheme in value: {value} {parts.scheme}")

        if parts.hostname:
            raise ValueError(f"Unexpected hostname in value: {value} {parts.hostname}")

        if parts.username:
            raise ValueError(f"Unexpected username in value: {value} {parts.username}")

        if parts.password:
            raise ValueError(f"Unexpected password in value: {value} {parts.password}")


def apply_fuzzy_rules(uri: HttpUrl | str) -> str:
    """Apply fuzzy rules on a URL or relative path

    First matching fuzzy rule matching the input value is applied and its result
    is returned.

    If no fuzzy rule is matching, the input is returned as-is.
    """
    value = uri.value if isinstance(uri, HttpUrl) else uri
    for rule in COMPILED_FUZZY_RULES:
        if match := rule["match"].match(value):
            return match.expand(rule["replace"])
    return value


def normalize(url: HttpUrl) -> ZimPath:
    """Transform a HTTP URL into a ZIM path to use as a entry's key.

    According to RFC 3986, a URL allows only a very limited set of characters, so we
    assume by default that the url is encoded to match this specification.

    The transformation rewrites the hostname, the path and the querystring.

    The transformation drops the URL scheme, username, password, port and fragment:
    - we suppose there is no conflict of URL scheme or port: there is no two ressources
     with same hostname, path and querystring but different URL scheme or port leading
     to different content
    - we consider username/password port are purely authentication mechanism which have
    no impact on the content to server
    - we know that the fragment is never passed to the server, it stays in the
    User-Agent, so if we encounter a fragment while normalizing a URL found in a
    document, it won't make its way to the ZIM anyway and will stay client-side

    The transformation consists mainly in decoding the three components so that ZIM path
    is not encoded at all, as required by the ZIM specification.

    Decoding is done differently for the hostname (decoded with puny encoding) and the
    path and querystring (both decoded with url decoding).

    The final transformation is the application of fuzzy rules (sourced from wabac) to
    transform some URLs into replay URLs and drop some useless stuff.

    Returned value is a ZIM path, without any puny/url encoding applied, ready to be
    passed to python-libzim for UTF-8 encoding.
    """

    url_parts = urlsplit(url.value)

    hostname = url_parts.hostname

    if hostname and hostname not in known_bad_hostnames:
        try:
            # try to decode the hostname
            hostname = idna.decode(hostname)
        except idna.IDNAError as exc:
            # exception might happen if illegal character are found in hostname like the
            # `_` in `host_ip` ; we keep the set of bad hostname in memory to not fill
            # the logs with these warnings
            logger.warning(f"Bad hostname found, kept as-is: {hostname}", exc_info=exc)
            known_bad_hostnames.add(hostname)

    path = url_parts.path

    if path:
        # unquote the path so that it is stored unencoded in the ZIM as required by ZIM
        # specification
        path = unquote(path)
    else:
        # if path is empty, we need a "/" to remove ambiguities, e.g. https://example.com
        # and https://example.com/ must all lead to the same ZIM entry to match RFC 3986
        # section 6.2.3 : https://www.rfc-editor.org/rfc/rfc3986#section-6.2.3
        path = "/"

    query = url_parts.query

    # if query is missing, we do not add it at all, not even a trailing ? without
    # anything after it
    if url_parts.query:
        # `+`` in query parameter must be decoded as space first to remove ambiguities
        # between a space (encoded as `+` in url query parameter) and a real plus sign
        # (encoded as %2B but soon decoded in ZIM path)
        query = query.replace("+", " ")
        # unquote the query so that it is stored unencoded in the ZIM as required by ZIM
        # specification
        query = "?" + unquote(query)
    else:
        query = ""

    fuzzified_url = apply_fuzzy_rules(f"{hostname}{path}{query}")

    return ZimPath(fuzzified_url)


def get_without_fragment(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(parsed._replace(fragment=""))


class ArticleUrlRewriter:
    """Rewrite urls in article."""

    def __init__(self, article_url: HttpUrl, existing_zim_paths: set[ZimPath]):
        self.article_path = normalize(article_url)
        self.article_url = article_url
        self.existing_zim_paths = existing_zim_paths
        self.missing_zim_paths: set[ZimPath] = set()

    def __call__(self, item_url: str, *, rewrite_all_url: bool = True) -> str:
        """Rewrite a url contained in a article.

        The url is "fully" rewrited to point to a normalized entry path
        """

        item_url = item_url.strip()

        item_scheme = urlsplit(item_url).scheme
        if item_scheme and item_scheme not in ("http", "https"):
            return item_url

        item_absolute_url = urljoin(self.article_url.value, item_url)
        item_fragment = urlsplit(item_absolute_url).fragment

        item_path = normalize(HttpUrl(item_absolute_url))

        if rewrite_all_url or item_path in self.existing_zim_paths:
            return self.get_document_uri(item_path, item_fragment)
        else:
            if item_path not in self.missing_zim_paths:
                logger.debug(f"WARNING {item_path} ({item_url}) not in archive.")
                # maintain a collection of missing Zim Path to not fill the logs with
                # duplicate messages
                self.missing_zim_paths.add(item_path)
            # The url doesn't point to a known entry
            return item_absolute_url

    def get_document_uri(self, item_path: ZimPath, item_fragment: str) -> str:
        """Given an ZIM item path and its fragment, get the URI to use in document

        This function transforms the path of a ZIM item we want to adress from current
        document (HTML / JS / ...) and returns the corresponding URI to use.

        It computes the relative path based on current document location and escape
        everything which needs to be to transform the ZIM path into a valid RFC 3986 URI

        It also append a potential trailing item fragment at the end of the resulting
        URI.

        """
        item_parts = urlsplit(item_path.value)

        # item_path is both path + querystring, both will be url-encoded in the document
        # so that readers consider them as a whole and properly pass them to libzim
        item_url = item_parts.path
        if item_parts.query:
            item_url += "?" + item_parts.query
        relative_path = str(
            PurePosixPath(item_url).relative_to(
                (
                    PurePosixPath(self.article_path.value)
                    if self.article_path.value.endswith("/")
                    else PurePosixPath(self.article_path.value).parent
                ),
                walk_up=True,
            )
        )
        # relative_to removes a potential last '/' in the path, we add it back
        if item_path.value.endswith("/"):
            relative_path += "/"

        return (
            f"{quote(relative_path, safe='/')}"
            f"{'#' + item_fragment if item_fragment else ''}"
        )
