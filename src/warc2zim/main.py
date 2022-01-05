#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim conversion utility

This utility provides a conversion from WARC records to ZIM files.
The WARCs are converted in a 'lossless' way, no data from WARC records is lost.
Each WARC record results in two ZIM articles:
- The WARC payload is stored under /A/<url>
- The WARC headers + HTTP headers are stored under the /H/<url>

Given a WARC response record for 'https://example.com/',
two ZIM articles are created /A/example.com/ and /H/example.com/ are created.

Only WARC response and resource records are stored.

If the WARC contains multiple entries for the same URL, only the first entry is added,
and later entries are ignored. A warning is printed as well.

"""

import os
import sys
import json
import pathlib
import logging
import tempfile
import datetime
import re
import io
import time
from argparse import ArgumentParser
from urllib.parse import urlsplit, urljoin, urlunsplit, urldefrag

import pkg_resources
import requests
from warcio import ArchiveIterator, StatusAndHeaders
from warcio.recordbuilder import RecordBuilder
from libzim.writer import Article, Blob
from zimscraperlib.types import get_mime_for_name
from zimscraperlib.zim.creator import Creator
from zimscraperlib.i18n import setlocale, get_language_details, Locale
from bs4 import BeautifulSoup

from jinja2 import Environment, PackageLoader

from cdxj_indexer import iter_file_or_dir, buffering_record_iter


# Shared logger
logger = logging.getLogger("warc2zim")

# HTML mime types
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")


# HTML raw mime type
HTML_RAW = "text/html;raw=true"


# external sw.js filename
SW_JS = "sw.js"

# head insert template
HEAD_INSERT_FILE = "sw_check.html"


HEAD_INS = re.compile(b"(<head>)", re.I)
CSS_INS = re.compile(b"(</head>)", re.I)


# Default ZIM metadata tags
DEFAULT_TAGS = ["_ftindex:yes", "_category:other", "_sw:yes"]


FUZZY_RULES = [
    {
        "match": re.compile(
            # r"//.*googlevideo.com/(videoplayback\?).*(id=[^&]+).*([&]itag=[^&]+).*"
            r"//.*googlevideo.com/(videoplayback\?).*((?<=[?&])id=[^&]+).*"
        ),
        "replace": r"//youtube.fuzzy.replayweb.page/\1\2",
    },
    {
        "match": re.compile(
            r"//(?:www\.)?youtube(?:-nocookie)?\.com/(get_video_info\?)"
            r".*(video_id=[^&]+).*"
        ),
        "replace": r"//youtube.fuzzy.replayweb.page/\1\2",
    },
    {"match": re.compile(r"(\.[^?]+\?)[\d]+$"), "replace": r"\1"},
    {
        "match": re.compile(
            r"//(?:www\.)?youtube(?:-nocookie)?\.com\/(youtubei\/[^?]+).*(videoId[^&]+).*"
        ),
        "replace": r"//youtube.fuzzy.replayweb.page/\1?\2",
    },
    {
        "match": re.compile(r"//(?:www\.)?youtube(?:-nocookie)?\.com/embed/([^?]+).*"),
        "replace": r"//youtube.fuzzy.replayweb.page/embed/\1",
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

CUSTOM_CSS_URL = "https://warc2zim.kiwix.app/custom.css"


# ============================================================================
class BaseArticle(Article):
    """BaseArticle for all ZIM Articles in warc2zim with default settings"""

    def is_redirect(self):
        return False

    def get_title(self):
        return ""

    def get_filename(self):
        return ""

    def should_compress(self):
        mime = self.get_mime_type()
        return mime.startswith("text/") or mime in (
            "application/warc-headers",
            "application/javascript",
            "application/json",
            "image/svg+xml",
        )

    def should_index(self):
        return False


# ============================================================================
class WARCHeadersArticle(BaseArticle):
    """WARCHeadersArticle used to store the WARC + HTTP headers as text
    Usually stored under H namespace
    """

    def __init__(self, record):
        super().__init__()
        self.record = record
        self.url = get_record_url(record)

    def get_url(self):
        return "H/" + canonicalize(self.url)

    def get_title(self):
        return ""

    def get_mime_type(self):
        return "application/warc-headers"

    def get_data(self):
        # add WARC headers
        buff = self.record.rec_headers.to_bytes(encoding="utf-8")
        # add HTTP headers, if present
        if self.record.http_headers:
            buff += self.record.http_headers.to_bytes(encoding="utf-8")

        return Blob(buff)


# ============================================================================
class WARCPayloadArticle(BaseArticle):
    """WARCPayloadArticle used to store the WARC payload
    Usually stored under A namespace
    """

    def __init__(self, record, head_insert=None, css_insert=None):
        super().__init__()
        self.record = record
        self.url = get_record_url(record)
        self.mime = get_record_mime_type(record)
        self.title = ""
        if hasattr(record, "buffered_stream"):
            self.record.buffered_stream.seek(0)
            self.payload = self.record.buffered_stream.read()
        else:
            self.payload = self.record.content_stream().read()

        if self.mime == "text/html":
            self.title = parse_title(self.payload)
            if head_insert:
                self.payload = HEAD_INS.sub(head_insert, self.payload)
            if css_insert:
                self.payload = CSS_INS.sub(css_insert, self.payload)

    def get_url(self):
        return "A/" + canonicalize(self.url)

    def get_title(self):
        return self.title

    def get_mime_type(self):
        # converting text/html to application/octet-stream to avoid rewriting by kiwix
        # original mime type still preserved in the headers block
        return HTML_RAW if self.mime == "text/html" else self.mime

    def get_data(self):
        return Blob(self.payload)

    def should_index(self):
        return self.mime in HTML_TYPES


# ============================================================================
class RemoteArticle(BaseArticle):
    def __init__(self, filename, url, mime=""):
        super().__init__()
        self.filename = filename
        self.url = url

        try:
            if url.startswith("http://") or url.startswith("https://"):
                resp = requests.get(url)
                resp.raise_for_status()
                self.content = resp.content
                self.mime = mime or resp.headers.get("Content-Type").split(";")[0]
            else:
                with open(url, "rt") as fh:
                    self.content = fh.read()
                self.mime = mime
                if not self.mime:
                    self.mime = get_mime_for_name(filename)

        except Exception as e:
            logger.error(e)
            logger.error("Unable to load URL: {0}".format(url))
            raise

    def get_url(self):
        return "A/" + self.filename

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        return Blob(self.content)


# ============================================================================
class StaticArticle(BaseArticle):
    def __init__(self, env, filename, main_url):
        super().__init__()
        self.filename = filename
        self.main_url = main_url

        self.mime = get_mime_for_name(filename)
        self.mime = self.mime or "application/octet-stream"

        if filename != SW_JS:
            template = env.get_template(filename)
            self.content = template.render(MAIN_URL=self.main_url)
        else:
            self.content = pkg_resources.resource_string(
                "warc2zim", "templates/" + filename
            ).decode("utf-8")

    def get_url(self):
        return "A/" + self.filename

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        return Blob(self.content.encode("utf-8"))


# ============================================================================
class RedirectArticle(BaseArticle):
    def __init__(self, from_url, to_url):
        super().__init__()
        self.from_url = from_url
        self.to_url = to_url

    def get_url(self):
        return self.from_url

    def is_redirect(self):
        return True

    def get_redirect_url(self):
        return self.to_url


# ============================================================================
class FaviconRedirectArticle(RedirectArticle):
    def __init__(self, favicon_url):
        super().__init__("-/favicon", "A/" + canonicalize(favicon_url))


# ============================================================================
class WARC2Zim:
    def __init__(self, args):
        logging.basicConfig(format="[%(levelname)s] %(message)s")
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        self.indexed_urls = set({})

        self.output = args.output
        self.zim_file = args.zim_file

        if not self.zim_file:
            self.zim_file = "{name}_{period}.zim".format(
                name=args.name, period=time.strftime("%Y-%m")
            )

        self.full_filename = os.path.join(self.output, self.zim_file)

        # ensure output file is writable
        with tempfile.NamedTemporaryFile(dir=self.output, delete=True) as fh:
            logger.debug(f"Confirming output is writable using {fh.name}")

        self.inputs = args.inputs
        self.replay_viewer_source = args.replay_viewer_source
        self.custom_css = args.custom_css

        self.main_url = args.url
        # ensure trailing slash is added if missing
        parts = urlsplit(self.main_url)
        if parts.path == "":
            parts = list(parts)
            # set path
            parts[2] = "/"
            self.main_url = urlunsplit(parts)

        self.include_domains = args.include_domains

        self.favicon_url = args.favicon
        self.language = args.lang
        self.title = args.title

        tags = DEFAULT_TAGS + (args.tags or [])

        self.metadata = {
            "name": args.name,
            "description": args.description,
            "creator": args.creator,
            "publisher": args.publisher,
            "tags": ";".join(tags),
            # optional
            "source": args.source,
            "scraper": "warc2zim " + get_version(),
        }

        self.replay_articles = []
        self.revisits = {}

        # progress file handling
        self.stats_filename = (
            pathlib.Path(args.progress_file) if args.progress_file else None
        )
        if self.stats_filename and not self.stats_filename.is_absolute():
            self.stats_filename = self.output / self.stats_filename
        self.written_records = self.total_records = 0

    def add_remote_or_local(self, filename, mime=""):
        if self.replay_viewer_source:
            article = RemoteArticle(
                filename, self.replay_viewer_source + filename, mime
            )
        else:
            article = StaticArticle(self.env, filename, self.main_url)

        self.replay_articles.append(article)

    def init_env(self):
        # autoescape=False to allow injecting html entities from translated text
        env = Environment(
            loader=PackageLoader("warc2zim", "templates"),
            extensions=["jinja2.ext.i18n"],
            autoescape=False,
        )

        try:
            env.install_gettext_translations(Locale.translation)
        except OSError:
            logger.warning(
                "No translations table found for language: {0}".format(self.language)
            )
            env.install_null_translations()

        return env

    def update_stats(self):
        """write progress as JSON to self.stats_filename if requested"""
        if not self.stats_filename:
            return
        self.written_records += 1
        with open(self.stats_filename, "w") as fh:
            json.dump(
                {"written": self.written_records, "total": self.total_records}, fh
            )

    def get_custom_css_record(self):
        if re.match(r"^https?\://", self.custom_css):
            resp = requests.get(self.custom_css, timeout=10)
            resp.raise_for_status()
            payload = resp.content
        else:
            css_path = pathlib.Path(self.custom_css).expanduser().resolve()
            with open(css_path, "rb") as fh:
                payload = fh.read()

        http_headers = StatusAndHeaders(
            "200 OK",
            [("Content-Type", 'text/css; charset="UTF-8"')],
            protocol="HTTP/1.0",
        )

        return RecordBuilder().create_warc_record(
            CUSTOM_CSS_URL,
            "response",
            payload=io.BytesIO(payload),
            length=len(payload),
            http_headers=http_headers,
        )

    def run(self):
        if not self.inputs:
            logger.info(
                "Arguments valid, no inputs to process. Exiting with error code 100"
            )
            return 100

        self.find_main_page_metadata()

        # make sure Language metadata is ISO-639-3 and setup translations
        try:
            lang_data = get_language_details(self.language)
            self.language = lang_data["iso-639-3"]
            setlocale(pathlib.Path(__file__).parent, lang_data.get("iso-639-1"))
        except Exception:
            logger.error(f"Invalid language setting `{self.language}`. Using `eng`.")

        self.env = self.init_env()

        # init head insert
        template = self.env.get_template(HEAD_INSERT_FILE)
        self.head_insert = ("<head>" + template.render()).encode("utf-8")
        if self.custom_css:
            self.css_insert = (
                f'\n<link type="text/css" href="{CUSTOM_CSS_URL}" '
                'rel="Stylesheet" />\n</head>'
            ).encode("utf-8")
        else:
            self.css_insert = None

        self.add_remote_or_local(SW_JS, "application/javascript")

        for filename in pkg_resources.resource_listdir("warc2zim", "templates"):
            if filename == HEAD_INSERT_FILE:
                continue

            if filename != SW_JS:
                self.replay_articles.append(
                    StaticArticle(self.env, filename, self.main_url)
                )

        with Creator(
            self.full_filename,
            main_page="index.html",
            language=self.language or "eng",
            title=self.title,
            date=datetime.date.today(),
            compression="zstd",
            **self.metadata,
        ) as zimcreator:

            for article in self.generate_all_articles():
                if article:
                    zimcreator.add_zim_article(article)
                    if isinstance(article, WARCPayloadArticle):
                        self.total_records += 1
                        self.update_stats()

            logger.debug(f"Found {self.total_records} records in WARCs")

    def iter_all_warc_records(self):
        # add custom css records
        if self.custom_css:
            yield self.get_custom_css_record()

        yield from iter_warc_records(self.inputs)

    def find_main_page_metadata(self):
        for record in self.iter_all_warc_records():
            if record.rec_type == "revisit":
                continue

            # if no main_url, use first 'text/html' record as the main page by default
            # not guaranteed to always work
            mime = get_record_mime_type(record)

            url = record.rec_headers["WARC-Target-URI"]

            if (
                not self.main_url
                and mime == "text/html"
                and record.payload_length != 0
                and (
                    not record.http_headers
                    or record.http_headers.get_statuscode() == "200"
                )
            ):
                self.main_url = url

            if urldefrag(self.main_url).url != url:
                continue

            # if we get here, found record for the main page

            # if main page is not html, still allow (eg. could be text, img),
            # but print warning
            if mime not in HTML_TYPES:
                logger.warning(
                    "Main page is not an HTML Page, mime type is: {0} "
                    "- Skipping Favicon and Language detection".format(mime)
                )
                return

            # content = record.content_stream().read()
            record.buffered_stream.seek(0)
            content = record.buffered_stream.read()

            if not self.title:
                self.title = parse_title(content)

            self.find_icon_and_language(content)

            logger.debug("Title: {0}".format(self.title))
            logger.debug("Language: {0}".format(self.language))
            logger.debug("Favicon: {0}".format(self.favicon_url))
            return

        msg = "Unable to find WARC record for main page: {0}, ZIM not created".format(
            self.main_url
        )
        logger.error(msg)
        raise KeyError(msg)

    def find_icon_and_language(self, content):
        soup = BeautifulSoup(content, "html.parser")

        if not self.favicon_url:
            # find icon
            icon = soup.find("link", rel="shortcut icon")
            if not icon:
                icon = soup.find("link", rel="icon")

            if icon:
                self.favicon_url = urljoin(self.main_url, icon.attrs["href"])
            else:
                self.favicon_url = urljoin(self.main_url, "/favicon.ico")

        if not self.language:
            # HTML5 Standard
            lang_elem = soup.find("html", attrs={"lang": True})
            if lang_elem:
                self.language = lang_elem.attrs["lang"]
                return

            # W3C recommendation
            lang_elem = soup.find(
                "meta", {"http-equiv": "content-language", "content": True}
            )
            if lang_elem:
                self.language = lang_elem.attrs["content"]
                return

            # SEO Recommendations
            lang_elem = soup.find("meta", {"name": "language", "content": True})
            if lang_elem:
                self.language = lang_elem.attrs["content"]
                return

    def generate_all_articles(self):
        # add replay system
        for article in self.replay_articles:
            yield article

        for record in self.iter_all_warc_records():
            yield from self.articles_for_warc_record(record)

        # process revisits, headers only
        for url, record in self.revisits.items():
            if url not in self.indexed_urls:
                logger.debug(
                    "Adding revisit {0} -> {1}".format(
                        url, record.rec_headers["WARC-Refers-To-Target-URI"]
                    )
                )
                yield WARCHeadersArticle(record)
                self.indexed_urls.add(url)

        if not self.favicon_url:
            return

        if self.favicon_url not in self.indexed_urls:
            logger.debug("Favicon not found in WARCs, fetching directly")
            try:
                yield RemoteArticle(canonicalize(self.favicon_url), self.favicon_url)
            except Exception:
                return

        yield FaviconRedirectArticle(self.favicon_url)

    def is_self_redirect(self, record, url):
        if record.rec_type != "response":
            return False

        if not record.http_headers.get_statuscode().startswith("3"):
            return False

        location = record.http_headers["Location"]
        return canonicalize(url) == canonicalize(location)

    def articles_for_warc_record(self, record):
        url = get_record_url(record)
        if not url:
            logger.debug(f"Skipping record with empty WARC-Target-URI {record}")
            return

        if url in self.indexed_urls:
            logger.debug("Skipping duplicate {0}, already added to ZIM".format(url))
            return

        # if include_domains is set, only include urls from those domains
        if self.include_domains:
            parts = urlsplit(url)
            if not any(
                parts.netloc.endswith(domain) for domain in self.include_domains
            ):
                logger.debug("Skipping url {0}, outside included domains".format(url))
                return

        if record.rec_type != "revisit":
            if self.is_self_redirect(record, url):
                logger.debug("Skipping self-redirect: " + url)
                return

            yield WARCHeadersArticle(record)
            payload_article = WARCPayloadArticle(
                record, self.head_insert, self.css_insert
            )

            if len(payload_article.payload) != 0:
                yield payload_article

            self.indexed_urls.add(url)

        elif (
            record.rec_headers["WARC-Refers-To-Target-URI"] != url
            and url not in self.revisits
        ):
            self.revisits[url] = record

        self.add_fuzzy_match_record(url)

    def add_fuzzy_match_record(self, url):
        fuzzy_url = url
        for rule in FUZZY_RULES:
            fuzzy_url = rule["match"].sub(rule["replace"], url)
            if fuzzy_url != url:
                break

        if fuzzy_url == url:
            return

        http_headers = StatusAndHeaders("302 Redirect", {"Location": url})

        date = datetime.datetime.utcnow().isoformat()
        builder = RecordBuilder()
        record = builder.create_revisit_record(
            fuzzy_url, "3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ", url, date, http_headers
        )

        self.revisits[fuzzy_url] = record
        logger.debug("Adding fuzzy redirect {0} -> {1}".format(fuzzy_url, url))


# ============================================================================
def get_record_url(record):
    """Check if record has url converted from POST/PUT, and if so, use that
    otherwise return the target url"""
    if hasattr(record, "urlkey"):
        return record.urlkey
    return record.rec_headers["WARC-Target-URI"]


# ============================================================================
def get_record_mime_type(record):
    if record.http_headers:
        # if the record has HTTP headers, use the Content-Type from those
        # (eg. 'response' record)
        content_type = record.http_headers["Content-Type"]
    else:
        # otherwise, use the Content-Type from WARC headers
        content_type = record.rec_headers["Content-Type"]

    mime = content_type or ""
    return mime.split(";")[0]


# ============================================================================
def parse_title(content):
    soup = BeautifulSoup(content, "html.parser")
    try:
        return soup.title.text or ""
    except AttributeError:
        return ""


# ============================================================================
def iter_warc_records(inputs):
    """iter warc records, including appending request data to matching response"""
    for filename in iter_file_or_dir(inputs):
        with open(filename, "rb") as fh:
            for record in buffering_record_iter(ArchiveIterator(fh), post_append=True):
                if record.rec_type in ("resource", "response", "revisit"):
                    yield record


# ============================================================================
def warc2zim(args=None):
    parser = ArgumentParser(description="Create ZIM files from WARC files")

    parser.add_argument("-V", "--version", action="version", version=get_version())
    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument(
        "inputs",
        nargs="*",
        help="""Paths of directories and/or files to be included in
                                the WARC file.""",
    )

    parser.add_argument(
        "-r",
        "--replay-viewer-source",
        help="""URL from which to load the ReplayWeb.page replay viewer from""",
    )

    parser.add_argument(
        "-u",
        "--url",
        help="""The main url that should be loaded in the viewer on init""",
    )

    parser.add_argument(
        "-i",
        "--include-domains",
        action="append",
        help="Limit ZIM file to URLs from only certain domains. "
        "If not set, all URLs in the input WARCs are included.",
    )

    parser.add_argument(
        "-f",
        "--favicon",
        help="URL for Favicon for Main Page. "
        "If unspecified, will attempt to use from main page. "
        "If not found in the ZIM, will attempt to load directly",
    )

    parser.add_argument(
        "--custom-css",
        help="URL or path to a CSS file to be added to ZIM "
        "and injected on every HTML page",
    )

    # output
    parser.add_argument("--name", help="The name of the ZIM", default="", required=True)
    parser.add_argument("--output", help="Output directory", default="/output")
    parser.add_argument("--zim-file", help="ZIM Filename", default="")

    # optional metadata
    parser.add_argument("--title", help="The Title", default="")
    parser.add_argument("--description", help="The Description", default="")
    parser.add_argument("--tags", action="append", help="One or more tags", default=[])
    parser.add_argument(
        "--lang",
        help="Language (should be a ISO-639-3 language code). "
        "If unspecified, will attempt to detect from main page, or use 'eng'",
        default="",
    )
    parser.add_argument("--publisher", help="ZIM publisher", default="Kiwix")
    parser.add_argument("--creator", help="ZIM creator", default="-")
    parser.add_argument("--source", help="ZIM source", default="")

    parser.add_argument(
        "--progress-file",
        help="Output path to write progress to. Relative to output if not absolute",
        default="",
    )

    r = parser.parse_args(args=args)
    warc2zim = WARC2Zim(r)
    return warc2zim.run()


# ============================================================================
def canonicalize(url):
    """Return a 'canonical' version of the url under which it is stored in the ZIM
    For now, just removing the scheme http:// or https:// scheme
    """
    if url.startswith("https://"):
        return url[8:]

    if url.startswith("http://"):
        return url[7:]

    return url


# ============================================================================
def get_version():
    return pkg_resources.get_distribution("warc2zim").version


# ============================================================================
if __name__ == "__main__":  # pragma: no cover
    sys.exit(warc2zim())
