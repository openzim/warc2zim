#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim conversion utility

This utility provides a conversion from WARC records to ZIM files.
WARC record are directly stored in a zim file as:
- Response WARC record as item "normalized" <url>
- Revisit record as alias (using "normalized" <url> to)

If the WARC contains multiple entries for the same URL, only the first entry is added,
and later entries are ignored. A warning is printed as well.
"""

import datetime
import importlib.resources
import io
import json
import logging
import pathlib
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import requests

# from zimscraperlib import getLogger
from bs4 import BeautifulSoup
from cdxj_indexer import buffering_record_iter, iter_file_or_dir
from jinja2 import Environment, PackageLoader
from warcio import ArchiveIterator, StatusAndHeaders
from warcio.recordbuilder import RecordBuilder
from zimscraperlib.constants import (
    DEFAULT_DEV_ZIM_METADATA,
    RECOMMENDED_MAX_TITLE_LENGTH,
)
from zimscraperlib.download import stream_file
from zimscraperlib.i18n import get_language_details
from zimscraperlib.image.convertion import convert_image
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.zim.creator import Creator
from zimscraperlib.zim.items import StaticItem

from warc2zim.constants import logger
from warc2zim.items import StaticArticle, WARCPayloadItem
from warc2zim.url_rewriting import FUZZY_RULES, normalize
from warc2zim.utils import (
    get_record_content,
    get_record_mime_type,
    get_record_url,
    get_version,
    parse_title,
)

# HTML mime types
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")

# head insert template
HEAD_INSERT_FILE = "head_insert.html"

# Default ZIM metadata tags
DEFAULT_TAGS = ["_ftindex:yes", "_category:other"]

CUSTOM_CSS_URL = "https://warc2zim.kiwix.app/custom.css"

DUPLICATE_EXC_STR = re.compile(
    r"^Impossible to add(.+)"
    r"dirent\'s title to add is(.+)"
    r"existing dirent's title is(.+)",
    re.MULTILINE | re.DOTALL,
)

ALIAS_EXC_STR = re.compile(
    r"^Impossible to alias(.+)(.+) doesn't exist.",
    re.MULTILINE | re.DOTALL,
)

PY2JS_RULE_RX = re.compile(r"\\(\d)", re.ASCII)


class Converter:
    def __init__(self, args):
        if args.verbose:
            # set log level in all configured handlers
            for handler in logger.handlers:
                handler.setLevel(logging.DEBUG)

        main_url: str = args.url
        # ensure trailing slash is added if missing
        parts = urlsplit(main_url)
        if parts.path == "":
            parts = list(parts)
            # set path
            parts[2] = "/"
            main_url = urlunsplit(parts)

        self.name = args.name
        self.title = args.title
        self.favicon_url = args.favicon
        self.language = args.lang
        self.description = args.description
        self.long_description = args.long_description
        self.creator_metadata = args.creator
        self.publisher = args.publisher
        self.tags = DEFAULT_TAGS + (args.tags or [])
        self.source: str = args.source or main_url
        self.scraper = "warc2zim " + get_version()
        self.illustration = b""
        self.main_url = normalize(main_url)

        self.output = Path(args.output)
        self.zim_file = args.zim_file

        if not self.zim_file:
            self.zim_file = "{name}_{period}.zim".format(
                name=self.name, period="{period}"
            )
        self.zim_file = self.zim_file.format(period=time.strftime("%Y-%m"))
        self.full_filename = self.output / self.zim_file

        # ensure output file is writable
        with tempfile.NamedTemporaryFile(dir=self.output, delete=True) as fh:
            logger.debug(f"Confirming output is writable using {fh.name}")

        self.inputs = args.inputs
        self.include_domains = args.include_domains

        self.custom_css = args.custom_css

        self.indexed_urls = set({})
        self.revisits = {}
        self.warc_urls = set({})

        # progress file handling
        self.stats_filename = (
            pathlib.Path(args.progress_file) if args.progress_file else None
        )
        if self.stats_filename and not self.stats_filename.is_absolute():
            self.stats_filename = self.output / self.stats_filename

        self.written_records = self.total_records = 0

    def init_env(self):
        # autoescape=False to allow injecting html entities from translated text
        env = Environment(
            loader=PackageLoader("warc2zim", "templates"),
            autoescape=False,  # noqa: S701
        )

        env.filters["urlsplit"] = urlsplit
        env.filters["tobool"] = lambda val: "true" if val else "false"

        env.filters["py2jsregex"] = lambda py_reg: PY2JS_RULE_RX.sub(r"$\1", py_reg)

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

        self.gather_information_from_warc()
        self.title = self.title or "Untitled"
        if len(self.title) > RECOMMENDED_MAX_TITLE_LENGTH:
            self.title = f"{self.title[0:29]}…"
        self.retrieve_illustration()
        self.convert_illustration()

        # make sure Language metadata is ISO-639-3
        try:
            lang_data = get_language_details(self.language)
            self.language = lang_data["iso-639-3"]
        except Exception:
            logger.error(f"Invalid language setting `{self.language}`. Using `eng`.")
            self.language = "eng"

        self.env = self.init_env()

        # init head insert
        self.head_template = self.env.get_template(HEAD_INSERT_FILE)
        if self.custom_css:
            self.css_insert = (
                f'\n<link type="text/css" href="{CUSTOM_CSS_URL}" rel="Stylesheet" />\n'
            )
        else:
            self.css_insert = None

        self.creator = Creator(
            self.full_filename,
            main_path=self.main_url,
        )

        self.creator.config_metadata(
            Name=self.name,
            Language=self.language or "eng",
            Title=self.title,
            Description=self.description,
            LongDescription=self.long_description,
            Creator=self.creator_metadata,
            Publisher=self.publisher,
            Date=datetime.date.today(),  # noqa: DTZ011
            Illustration_48x48_at_1=self.illustration,
            Tags=";".join(self.tags),
            Source=self.source,
            Scraper=f"warc2zim {get_version()}",
        ).start()

        for filename in importlib.resources.files("warc2zim.statics").iterdir():
            with importlib.resources.as_file(filename) as file:
                self.creator.add_item(StaticArticle(file, self.main_url))

        # Add wombat_setup.js
        wombat_setup_template = self.env.get_template("wombat_setup.js")
        wombat_setup_content = wombat_setup_template.render(FUZZY_RULES=FUZZY_RULES)
        self.creator.add_item(
            StaticItem(
                path="_zim_static/wombat_setup.js",  # pyright: ignore [reportArgumentType, reportGeneralTypeIssues]
                content=wombat_setup_content,  # pyright: ignore [reportArgumentType, reportGeneralTypeIssues]
                mimetype="text/javascript",  # pyright: ignore [reportArgumentType, reportGeneralTypeIssues]
            )
        )

        for record in self.iter_all_warc_records():
            self.add_items_for_warc_record(record)

        # process revisits
        for normalized_url, target_url in self.revisits.items():
            if normalized_url not in self.indexed_urls:
                logger.debug(f"Adding alias {normalized_url} -> {target_url}")
                try:
                    self.creator.add_alias(normalized_url, "", target_url, {})
                except RuntimeError as exc:
                    if not ALIAS_EXC_STR.match(str(exc)):
                        raise exc
                self.indexed_urls.add(normalized_url)

        logger.debug(f"Found {self.total_records} records in WARCs")

        self.creator.finish()

    def iter_all_warc_records(self):
        # add custom css records
        if self.custom_css:
            yield self.get_custom_css_record()

        yield from iter_warc_records(self.inputs)

    def gather_information_from_warc(self):
        main_page_found = False
        for record in iter_warc_records(self.inputs):
            url = get_record_url(record)
            normalized_url = normalize(url)

            self.warc_urls.add(normalized_url)

            if main_page_found:
                continue

            if record.rec_type == "revisit":
                continue

            # if no main_url, use first 'text/html' record as the main page by default
            # not guaranteed to always work
            mime = get_record_mime_type(record)

            if (
                not self.main_url
                and mime == "text/html"
                and record.payload_length != 0
                and (
                    not record.http_headers
                    or record.http_headers.get_statuscode() == "200"
                )
            ):
                self.main_url = normalized_url

            if urldefrag(self.main_url).url != normalized_url:
                continue

            # if we get here, found record for the main page

            # if main page is not html, still allow (eg. could be text, img),
            # but print warning
            if mime not in HTML_TYPES:
                logger.warning(
                    f"Main page is not an HTML Page, mime type is: {mime} "
                    "- Skipping Favicon and Language detection"
                )
                main_page_found = True
                continue

            content = get_record_content(record)

            if not self.title:
                self.title = parse_title(content)

            self.find_icon_and_language(content)

            logger.debug(f"Title: {self.title}")
            logger.debug(f"Language: {self.language}")
            logger.debug(f"Favicon: {self.favicon_url}")
            main_page_found = True

        if not main_page_found:
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

            if (
                icon
                and icon.attrs.get(  # pyright: ignore[reportGeneralTypeIssues, reportAttributeAccessIssue]
                    "href"
                )
            ):
                self.favicon_url = urljoin(
                    self.main_url,
                    icon.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                        "href"
                    ],
                )
            else:
                self.favicon_url = urljoin(self.main_url, "/favicon.ico")

        if not self.language:
            # HTML5 Standard
            lang_elem = soup.find("html", attrs={"lang": True})
            if lang_elem:
                self.language = lang_elem.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                    "lang"
                ]
                return

            # W3C recommendation
            lang_elem = soup.find(
                "meta", {"http-equiv": "content-language", "content": True}
            )
            if lang_elem:
                self.language = lang_elem.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                    "content"
                ]
                return

            # SEO Recommendations
            lang_elem = soup.find("meta", {"name": "language", "content": True})
            if lang_elem:
                self.language = lang_elem.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                    "content"
                ]
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
                self.illustration = get_record_content(record)

        # favicon_url not in WARC ; downloading
        try:
            dst = io.BytesIO()
            if not stream_file(self.favicon_url, byte_stream=dst)[0]:
                raise OSError(
                    "No bytes received downloading favicon"
                )  # pragma: no cover
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
            convert_image(
                src,  # pyright: ignore[reportGeneralTypeIssues, reportArgumentType]
                dst,  # pyright: ignore[reportGeneralTypeIssues, reportArgumentType]
                fmt="PNG",  # pyright: ignore[reportGeneralTypeIssues, reportArgumentType]
            )
            resize_image(dst, width=48, height=48, method="cover")
        except Exception as exc:  # pragma: no cover
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
        return normalize(url) == normalize(location)

    def add_items_for_warc_record(self, record):
        url = get_record_url(record)
        normalized_url = normalize(url)
        if not url:
            logger.debug(f"Skipping record with empty WARC-Target-URI {record}")
            return

        if normalized_url in self.indexed_urls:
            logger.debug(f"Skipping duplicate {url}, already added to ZIM")
            return

        # if include_domains is set, only include urls from those domains
        if self.include_domains:
            parts = urlsplit(url)
            if not any(
                parts.netloc.endswith(domain) for domain in self.include_domains
            ):
                logger.debug(f"Skipping url {url}, outside included domains")
                return

        if record.rec_type != "revisit":
            if self.is_self_redirect(record, url):
                logger.debug("Skipping self-redirect: " + url)
                return

            payload_item = WARCPayloadItem(
                normalized_url,
                record,
                self.head_template,
                self.css_insert,
                self.warc_urls,
            )

            if len(payload_item.content) != 0:
                try:
                    self.creator.add_item(payload_item)
                except RuntimeError as exc:
                    if not DUPLICATE_EXC_STR.match(str(exc)):
                        raise exc
                self.total_records += 1
                self.update_stats()

            self.indexed_urls.add(normalized_url)

        elif (
            record.rec_headers["WARC-Refers-To-Target-URI"] != url
            and normalized_url not in self.revisits
        ):  # pragma: no branch
            self.revisits[normalized_url] = normalize(
                record.rec_headers["WARC-Refers-To-Target-URI"]
            )


def iter_warc_records(inputs):
    """iter warc records, including appending request data to matching response"""
    for filename in iter_file_or_dir(inputs):
        with open(filename, "rb") as fh:
            for record in buffering_record_iter(ArchiveIterator(fh), post_append=True):
                if record and record.rec_type in ("resource", "response", "revisit"):
                    yield record
