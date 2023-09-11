#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim conversion utility

This utility provides a conversion from WARC records to ZIM files.
The WARCs are converted in a 'lossless' way, no data from WARC records is lost.
Each WARC record results in two ZIM items:
- The WARC payload is stored under /A/<url>
- The WARC headers + HTTP headers are stored under the /H/<url>

Given a WARC response record for 'https://example.com/',
two ZIM items are created /A/example.com/ and /H/example.com/ are created.

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
from libzim.writer import Hint
from warcio import ArchiveIterator, StatusAndHeaders
from warcio.recordbuilder import RecordBuilder
from zimscraperlib.constants import DEFAULT_DEV_ZIM_METADATA
from zimscraperlib.download import stream_file
from zimscraperlib.types import get_mime_for_name
from zimscraperlib.i18n import setlocale, get_language_details, Locale
from zimscraperlib.image.convertion import convert_image
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.zim.creator import Creator
from zimscraperlib.zim.items import StaticItem, URLItem
from zimscraperlib.zim.providers import StringProvider
from bs4 import BeautifulSoup

from jinja2 import Environment, PackageLoader

from cdxj_indexer import iter_file_or_dir, buffering_record_iter


# Shared logger
logger = logging.getLogger("warc2zim")

# HTML mime types
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")

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

DUPLICATE_EXC_STR = re.compile(
    r"^Impossible to add(.+)"
    r"dirent\'s title to add is(.+)"
    r"existing dirent's title is(.+)",
    re.MULTILINE | re.DOTALL,
)


# ============================================================================
class WARCHeadersItem(StaticItem):
    """WARCHeadersItem used to store the WARC + HTTP headers as text
    Usually stored under H namespace
    """

    def __init__(self, record):
        super().__init__()
        self.record = record
        self.url = get_record_url(record)

    def get_path(self):
        return "H/" + canonicalize(self.url)

    def get_title(self):
        return ""

    def get_mimetype(self):
        return "application/warc-headers"

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: False}

    def get_contentprovider(self):
        # add WARC headers
        buff = self.record.rec_headers.to_bytes(encoding="utf-8")
        # add HTTP headers, if present
        if self.record.http_headers:
            buff += self.record.http_headers.to_bytes(encoding="utf-8")

        return StringProvider(content=buff, ref=self)


# ============================================================================
class WARCPayloadItem(StaticItem):
    """WARCPayloadItem used to store the WARC payload
    Usually stored under A namespace
    """

    def __init__(self, record, head_insert=None, css_insert=None):
        super().__init__()
        self.record = record
        self.url = get_record_url(record)
        self.mimetype = get_record_mime_type(record)
        self.title = ""

        if hasattr(self.record, "buffered_stream"):
            self.record.buffered_stream.seek(0)
            self.content = self.record.buffered_stream.read()
        else:
            self.content = self.record.content_stream().read()

        if self.mimetype.startswith("text/html"):
            self.title = parse_title(self.content)
            if head_insert:
                self.content = HEAD_INS.sub(head_insert, self.content)
            if css_insert:
                self.content = CSS_INS.sub(css_insert, self.content)

    def get_path(self):
        return "A/" + canonicalize(self.url)

    def get_title(self):
        return self.title

    def get_hints(self):
        is_front = self.mimetype.startswith("text/html")
        return {Hint.FRONT_ARTICLE: is_front}


# ============================================================================
class StaticArticle(StaticItem):
    def __init__(self, env, filename, main_url, **kwargs):
        super().__init__(**kwargs)
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

    def get_path(self):
        return "A/" + self.filename

    def get_mimetype(self):
        return self.mime

    def get_hints(self):
        return {Hint.FRONT_ARTICLE: False}


# ============================================================================
class WARC2Zim:
    def __init__(self, args):
        logging.basicConfig(format="[%(levelname)s] %(message)s")
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        self.main_url = args.url
        # ensure trailing slash is added if missing
        parts = urlsplit(self.main_url)
        if parts.path == "":
            parts = list(parts)
            # set path
            parts[2] = "/"
            self.main_url = urlunsplit(parts)

        self.name = args.name
        self.title = args.title
        self.favicon_url = args.favicon
        self.language = args.lang
        self.description = args.description
        self.long_description = args.long_description
        self.creator_metadata = args.creator
        self.publisher = args.publisher
        self.tags = DEFAULT_TAGS + (args.tags or [])
        self.source = args.source or self.main_url
        self.scraper = "warc2zim " + get_version()
        self.illustration = b""

        self.output = args.output
        self.zim_file = args.zim_file

        if not self.zim_file:
            self.zim_file = "{name}_{period}.zim".format(
                name=self.name, period="{period}"
            )
        self.zim_file = self.zim_file.format(period=time.strftime("%Y-%m"))
        self.full_filename = os.path.join(self.output, self.zim_file)

        # ensure output file is writable
        with tempfile.NamedTemporaryFile(dir=self.output, delete=True) as fh:
            logger.debug(f"Confirming output is writable using {fh.name}")

        self.inputs = args.inputs
        self.include_domains = args.include_domains

        self.replay_viewer_source = args.replay_viewer_source
        self.custom_css = args.custom_css

        self.indexed_urls = set({})
        self.revisits = {}

        # progress file handling
        self.stats_filename = (
            pathlib.Path(args.progress_file) if args.progress_file else None
        )
        if self.stats_filename and not self.stats_filename.is_absolute():
            self.stats_filename = self.output / self.stats_filename

        self.written_records = self.total_records = 0

    def add_replayer(self):
        if self.replay_viewer_source and re.match(
            r"^https?\:", self.replay_viewer_source
        ):
            self.creator.add_item(
                URLItem(
                    url=self.replay_viewer_source + SW_JS,
                    path="A/" + SW_JS,
                    mimetype="application/javascript",
                )
            )
        elif self.replay_viewer_source:
            self.creator.add_item_for(
                fpath=self.replay_viewer_source + SW_JS,
                path="A/" + SW_JS,
                mimetype="application/javascript",
            )
        else:
            self.creator.add_item(
                StaticArticle(
                    self.env, SW_JS, self.main_url, mimetype="application/javascript"
                )
            )

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
        self.title = self.title or "Untitled"
        if len(self.title) > 30:
            self.title = f"{self.title[0:29]}…"
        self.retrieve_illustration()
        self.convert_illustration()

        # make sure Language metadata is ISO-639-3 and setup translations
        try:
            lang_data = get_language_details(self.language)
            self.language = lang_data["iso-639-3"]
        except Exception:
            logger.error(f"Invalid language setting `{self.language}`. Using `eng`.")
            self.language = "eng"

        # try to set locale to language. Might fail (missing locale)
        try:
            setlocale(pathlib.Path(__file__).parent, lang_data.get("iso-639-1"))
        except Exception:
            ...

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

        self.creator = Creator(
            self.full_filename,
            main_path="A/index.html",
        )

        self.creator.config_metadata(
            Name=self.name,
            Language=self.language or "eng",
            Title=self.title,
            Description=self.description,
            LongDescription=self.long_description,
            Creator=self.creator_metadata,
            Publisher=self.publisher,
            Date=datetime.date.today(),
            Illustration_48x48_at_1=self.illustration,
            Tags=";".join(self.tags),
            Source=self.source,
            Scraper=f"warc2zim {get_version()}",
        ).start()

        self.add_replayer()

        for filename in pkg_resources.resource_listdir("warc2zim", "templates"):
            if filename == HEAD_INSERT_FILE or filename == SW_JS:
                continue

            self.creator.add_item(StaticArticle(self.env, filename, self.main_url))

        for record in self.iter_all_warc_records():
            self.add_items_for_warc_record(record)

        # process revisits, headers only
        for url, record in self.revisits.items():
            if canonicalize(url) not in self.indexed_urls:
                logger.debug(
                    "Adding revisit {0} -> {1}".format(
                        url, record.rec_headers["WARC-Refers-To-Target-URI"]
                    )
                )
                try:
                    self.creator.add_item(WARCHeadersItem(record))
                except RuntimeError as exc:
                    if not DUPLICATE_EXC_STR.match(str(exc)):
                        raise exc
                self.indexed_urls.add(canonicalize(url))

        logger.debug(f"Found {self.total_records} records in WARCs")

        self.creator.finish()

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

            record.buffered_stream.seek(0)
            content = record.buffered_stream.read()

            if not self.title:
                self.title = parse_title(content)

            self.find_icon_and_language(content)

            logger.debug("Title: {0}".format(self.title))
            logger.debug("Language: {0}".format(self.language))
            logger.debug("Favicon: {0}".format(self.favicon_url))
            return

        raise KeyError(
            f"Unable to find WARC record for main page: {self.main_url}, aborting"
        )

    def find_icon_and_language(self, content):
        soup = BeautifulSoup(content, "html.parser")

        if not self.favicon_url:
            # find icon
            icon = soup.find("link", rel="shortcut icon")
            if not icon:
                icon = soup.find("link", rel="icon")

            if icon and icon.attrs.get("href"):
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

    def retrieve_illustration(self):
        """sets self.illustration from self.favicon_url either from WARC or download

        Uses fallback in case of errors/missing"""
        if not self.favicon_url:
            self.favicon_url = "fallback.png"
            self.illustration = DEFAULT_DEV_ZIM_METADATA["Illustration_48x48_at_1"]
            return
        # look into WARC records first
        for record in self.iter_all_warc_records():
            url = get_record_url(record)
            if not url or record.rec_type == "revisit":
                continue
            if url == self.favicon_url:
                logger.debug(f"Found WARC record for favicon: {self.favicon_url}")
                if record and record.http_headers.get_statuscode() != "200":
                    logger.warning("WARC record for favicon is unuable. Skipping")
                    self.favicon_url = "fallback.png"
                    self.illustration = DEFAULT_DEV_ZIM_METADATA[
                        "Illustration_48x48_at_1"
                    ]
                    return
                if hasattr(record, "buffered_stream"):
                    record.buffered_stream.seek(0)
                    self.illustration = record.buffered_stream.read()
                else:
                    self.illustration = record.content_stream().read()
                return

        # favicon_url not in WARC ; downloading
        try:
            dst = io.BytesIO()
            if not stream_file(self.favicon_url, byte_stream=dst)[0]:
                raise IOError("No bytes received downloading favicon")
            self.illustration = dst.getvalue()
        except Exception as exc:
            logger.warning(f"Unable to retrieve favicon. Using fallback: {exc}")
            self.favicon_url = "fallback.png"
            self.illustration = DEFAULT_DEV_ZIM_METADATA["Illustration_48x48_at_1"]
            return

    def convert_illustration(self):
        """convert self.illustration into a 48x48px PNG with fallback"""
        src = io.BytesIO(self.illustration)
        dst = io.BytesIO()
        try:
            convert_image(src, dst, fmt="PNG")
            resize_image(dst, width=48, height=48, method="cover")
        except Exception as exc:
            logger.warning(f"Failed to convert or resize favicon: {exc}")
            self.illustration = DEFAULT_DEV_ZIM_METADATA["Illustration_48x48_at_1"]
        else:
            self.illustration = dst.getvalue()

    def is_self_redirect(self, record, url):
        if record.rec_type != "response":
            return False

        if (
            not record.http_headers.get_statuscode().startswith("3")
            or record.http_headers.get_statuscode() == "300"
        ):
            return False

        location = record.http_headers.get("Location", "")
        return canonicalize(url) == canonicalize(location)

    def add_items_for_warc_record(self, record):
        url = get_record_url(record)
        if not url:
            logger.debug(f"Skipping record with empty WARC-Target-URI {record}")
            return

        if canonicalize(url) in self.indexed_urls:
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

            try:
                self.creator.add_item(WARCHeadersItem(record))
            except RuntimeError as exc:
                if not DUPLICATE_EXC_STR.match(str(exc)):
                    raise exc

            payload_item = WARCPayloadItem(record, self.head_insert, self.css_insert)

            if len(payload_item.content) != 0:
                try:
                    self.creator.add_item(payload_item)
                except RuntimeError as exc:
                    if not DUPLICATE_EXC_STR.match(str(exc)):
                        raise exc
                self.total_records += 1
                self.update_stats()

            self.indexed_urls.add(canonicalize(url))

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
    parser.add_argument("--name", help="ZIM Name metadata", default="", required=True)
    parser.add_argument("--output", help="Output directory", default="/output")
    parser.add_argument("--zim-file", help="ZIM Filename", default="")

    # optional metadata
    parser.add_argument("--title", help="ZIM Title", default="")
    parser.add_argument(
        "--description", help="ZIM Description (<=30 chars)", default="-"
    )
    parser.add_argument("--long-description", help="Longer description (<=4K chars)")
    parser.add_argument(
        "--tags", action="append", help="ZIM tags (use multiple times)", default=[]
    )
    parser.add_argument(
        "--lang",
        help="ZIM Language (should be a ISO-639-3 language code). "
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
