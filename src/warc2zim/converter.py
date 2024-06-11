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
import mimetypes
import os
import pathlib
import re
import sys
import tempfile
import time
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

import requests

# from zimscraperlib import getLogger
from bs4 import BeautifulSoup
from cdxj_indexer import buffering_record_iter, iter_file_or_dir
from jinja2 import Environment, PackageLoader
from warcio import ArchiveIterator
from zimscraperlib.constants import (
    DEFAULT_DEV_ZIM_METADATA,
    RECOMMENDED_MAX_TITLE_LENGTH,
)
from zimscraperlib.download import stream_file
from zimscraperlib.image.convertion import convert_image
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.types import FALLBACK_MIME
from zimscraperlib.zim.creator import Creator
from zimscraperlib.zim.metadata import (
    validate_description,
    validate_language,
    validate_longdescription,
    validate_tags,
    validate_title,
)

from warc2zim.constants import logger
from warc2zim.items import StaticArticle, StaticFile, WARCPayloadItem
from warc2zim.language import parse_language
from warc2zim.url_rewriting import HttpUrl, ZimPath, normalize
from warc2zim.utils import (
    can_process_status_code,
    get_record_content,
    get_record_mime_type,
    get_record_url,
    get_status_code,
    get_version,
    parse_title,
    status_code_is_processable_redirect,
)

# HTML mime types
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")

# head insert template
HEAD_INSERT_FILE = "head_insert.html"

# Default ZIM metadata tags
DEFAULT_TAGS = ["_ftindex:yes", "_category:other"]

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

        main_url: str | None = str(args.url) if args.url else None
        # ensure trailing slash is added if missing
        if main_url:
            parts = urlsplit(main_url)
            if parts.path == "":
                parts = list(parts)
                # set path
                parts[2] = "/"
                main_url = urlunsplit(parts)

        self.name = args.name
        self.title = args.title
        self.favicon_url = args.favicon
        self.favicon_path = None
        self.language = args.lang
        self.description = args.description
        self.long_description = args.long_description
        self.creator_metadata = args.creator
        self.publisher = args.publisher
        self.tags = {
            tag
            for tag in DEFAULT_TAGS + [tag.strip() for tag in args.tags.split(";")]
            if tag  # ignore empty tag
        }
        self.source: str | None = str(args.source) if args.source else None or main_url
        self.scraper = "warc2zim " + get_version()
        self.illustration = b""
        self.main_path = normalize(HttpUrl(main_url)) if main_url else None

        self.output = Path(args.output)
        self.zim_file = args.zim_file

        if not self.zim_file:
            self.zim_file = "{name}_{period}.zim".format(
                name=self.name, period="{period}"
            )
        self.zim_file = self.zim_file.format(period=time.strftime("%Y-%m"))
        self.full_filename = self.output / self.zim_file

        # ensure output file exists
        if not os.path.isdir(self.output):
            logger.error(
                f"Output directory {self.output} does not exist. Exiting with error "
                "code 1"
            )
            sys.exit(1)

        logger.debug(
            f"Attempting to confirm output is writable in directory {self.output}"
        )

        try:
            # ensure output file is writable
            with tempfile.NamedTemporaryFile(dir=self.output, delete=True) as fh:
                logger.debug(
                    f"Output is writable. Temporary file used for test: {fh.name}"
                )
        except Exception:
            logger.error(
                f"Failed to write to output directory {self.output}. Make sure output "
                "directory is writable. Exiting with error code 1"
            )
            sys.exit(1)

        # ensure ZIM file is creatable with the given name
        try:
            file_path = pathlib.Path(self.full_filename)
            file_path.touch()
            file_path.unlink()
            logger.debug(
                f"Confirming ZIM file can be created using name: {self.zim_file}"
            )
        except Exception:
            logger.error(
                f"Failed to create ZIM file with name: {self.zim_file}. Make sure the "
                "file name is valid."
            )
            raise SystemExit(3)  # noqa: B904

        self.failed_content_path = self.output / args.failed_items
        self.failed_content_path.mkdir(parents=True, exist_ok=True)

        self.inputs = args.inputs
        self.include_domains = args.include_domains

        self.custom_css = args.custom_css

        self.added_zim_items: set[ZimPath] = set()
        self.revisits: dict[ZimPath, ZimPath] = {}
        self.expected_zim_items: set[ZimPath] = set()
        self.redirections: dict[ZimPath, ZimPath] = {}
        self.missing_zim_paths: set[ZimPath] | None = set() if args.verbose else None
        self.js_modules: set[ZimPath] = set()

        # progress file handling
        self.stats_filename = (
            pathlib.Path(args.progress_file) if args.progress_file else None
        )
        if self.stats_filename and not self.stats_filename.is_absolute():
            self.stats_filename = self.output / self.stats_filename

        self.written_records = self.total_records = 0

        self.scraper_suffix = args.scraper_suffix

        self.continue_on_error = bool(args.continue_on_error)
        self.disable_metadata_checks = bool(args.disable_metadata_checks)

    def update_stats(self):
        """write progress as JSON to self.stats_filename if requested"""
        if not self.stats_filename:
            return
        self.written_records += 1
        with open(self.stats_filename, "w") as fh:
            json.dump(
                {"written": self.written_records, "total": self.total_records}, fh
            )

    def add_custom_css_item(self):
        if re.match(r"^https?\://", self.custom_css):
            resp = requests.get(self.custom_css, timeout=10)
            resp.raise_for_status()
            payload = resp.content
        else:
            css_path = pathlib.Path(self.custom_css).expanduser().resolve()
            with open(css_path, "rb") as fh:
                payload = fh.read()

        self.creator.add_item(
            StaticFile(content=payload, filename="custom.css", mimetype="text/css")
        )

    def run(self):

        if not self.disable_metadata_checks:
            # Validate ZIM metadata early so that we do not waste time doing operations
            # for a scraper which will fail anyway in the end
            validate_tags("Tags", self.tags)
            if self.title:
                validate_title("Title", self.title)
            if self.description:
                validate_description("Description", self.description)
            if self.long_description:
                validate_longdescription("LongDescription", self.long_description)
            if self.language:
                self.language = parse_language(self.language)
                validate_language("Language", self.language)
            # Nota: we do not validate illustration since logic in the scraper is made
            # to always provide a valid image, at least a fallback transparent PNG and
            # final illustration is most probably not yet known at this stage

        if not self.inputs:
            logger.info(
                "Arguments valid, no inputs to process. Exiting with return code 100"
            )
            return 100

        self.gather_information_from_warc()
        # validate language again, should it have been automatically retrieved from WARC
        validate_language("Language", self.language)
        if not self.main_path:
            raise ValueError("Unable to find main path, aborting")
        self.title = self.title or "Untitled"
        if len(self.title) > RECOMMENDED_MAX_TITLE_LENGTH:
            self.title = f"{self.title[0:29]}…"
        self.retrieve_illustration()
        self.convert_illustration()

        # autoescape=False to allow injecting html entities from translated text
        self.env = Environment(
            loader=PackageLoader("warc2zim", "templates"),
            autoescape=False,  # noqa: S701
        )

        self.env.filters["urlsplit"] = urlsplit
        self.env.filters["tobool"] = lambda val: "true" if val else "false"

        # init head inserts
        self.pre_head_template = self.env.get_template(HEAD_INSERT_FILE)
        self.post_head_template = self.env.from_string(
            '\n<link type="text/css" href="{{ static_prefix }}custom.css"'
            ' rel="stylesheet" />\n'
            if self.custom_css
            else ""
        )

        self.creator = Creator(
            self.full_filename,
            main_path=self.main_path.value,
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
            Tags=self.tags,
            Source=self.source,
            Scraper=f"warc2zim {get_version()}{self.scraper_suffix or ''}",
        ).start()

        for filename in importlib.resources.files("warc2zim.statics").iterdir():
            with importlib.resources.as_file(filename) as file:
                self.creator.add_item(
                    StaticArticle(filename=file, main_path=self.main_path.value)
                )

        if self.custom_css:
            self.add_custom_css_item()

        for record in iter_warc_records(self.inputs):
            try:
                self.add_items_for_warc_record(record)
            except Exception as exc:
                logger.error(
                    f"Problem encountered while processing {get_record_url(record)}.",
                    exc_info=exc,
                )
                if logger.isEnabledFor(logging.DEBUG):
                    content_extension = mimetypes.guess_extension(
                        get_record_mime_type(record), strict=False
                    ) or mimetypes.guess_extension(FALLBACK_MIME)
                    content_path = (
                        self.failed_content_path / f"{uuid4()}{content_extension}"
                    )
                    content_path.write_bytes(get_record_content(record))
                    logger.debug(
                        f"### REC Headers ###\n{record.rec_headers}\n"
                        f"### HTTP Headers ###\n{record.http_headers}\n"
                        "### Content ###\n"
                        f"Content has been stored b64-encoded at {content_path}"
                    )
                if not self.continue_on_error:
                    logger.error(
                        "Scraper will stop. Pass --verbose flag for more details."
                    )
                    raise

        # process redirects
        for redirect_source, redirect_target in self.redirections.items():
            self.creator.add_redirect(
                redirect_source.value, redirect_target.value, is_front=False
            )
            self.added_zim_items.add(redirect_source)

        # process revisits
        for normalized_url, target_url in self.revisits.items():
            if normalized_url not in self.added_zim_items:
                logger.debug(f"Adding alias {normalized_url} -> {target_url}")
                try:
                    self.creator.add_alias(
                        normalized_url.value, "", target_url.value, {}
                    )
                except RuntimeError as exc:
                    if not ALIAS_EXC_STR.match(str(exc)):
                        raise exc
                self.added_zim_items.add(normalized_url)

        logger.debug(f"Found {self.total_records} records in WARCs")

        self.creator.finish()

    def gather_information_from_warc(self):
        main_page_found = False
        for record in iter_warc_records(self.inputs):

            # only response records can be considered as main_path and as existing ZIM
            # path
            if record.rec_type not in ("response", "revisit"):
                continue

            url = get_record_url(record)
            zim_path = normalize(HttpUrl(url))

            status_code = get_status_code(record)
            if not can_process_status_code(status_code):
                continue

            if status_code_is_processable_redirect(status_code):
                # check for duplicates, might happen due to fuzzy rules
                if zim_path not in self.redirections:
                    if redirect_location := record.http_headers.get("Location"):
                        redirection_zim_path = normalize(
                            HttpUrl(urljoin(url, redirect_location))
                        )
                        # Redirection to same ZIM path have to be ignored (occurs for
                        # instance when redirecting from http to https)
                        if zim_path != redirection_zim_path:
                            self.redirections[zim_path] = redirection_zim_path
                    else:
                        logger.warning(f"Redirection target is empty for {zim_path}")
            else:
                self.expected_zim_items.add(zim_path)

            if main_page_found:
                continue

            if record.rec_type == "revisit":
                continue

            # if no main_path, use first 'text/html' record as the main page by default
            # not guaranteed to always work
            mime = get_record_mime_type(record)

            if (
                not self.main_path
                and mime == "text/html"
                and record.payload_length != 0
                and (
                    not record.http_headers
                    or record.http_headers.get_statuscode() == "200"
                )
            ):
                self.main_path = zim_path

            if self.main_path != zim_path:
                continue

            # if we get here, found record for the main page

            # if main page is a redirect, update the main url accordingly
            if record.http_headers:
                status_code = int(record.http_headers.get_statuscode())
                if status_code in [
                    HTTPStatus.MOVED_PERMANENTLY,
                    HTTPStatus.TEMPORARY_REDIRECT,
                    HTTPStatus.FOUND,
                ]:
                    original_path = self.main_path
                    self.main_path = normalize(
                        HttpUrl(
                            urljoin(
                                get_record_url(record),
                                record.http_headers.get_header("Location").strip(),
                            )
                        )
                    )
                    logger.warning(
                        f"HTTP {status_code} occurred on main page; "
                        f"replacing {original_path} with {self.main_path}"
                    )
                    continue

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

            self.find_icon_and_language(record, content)

            logger.debug(f"Title: {self.title}")
            logger.debug(f"Language: {self.language}")
            logger.debug(f"Favicon: {self.favicon_url or self.favicon_path}")
            main_page_found = True

        logger.info(f"Expecting {len(self.expected_zim_items)} ZIM entries to files")

        if not main_page_found:
            raise KeyError(
                f"Unable to find WARC record for main page: {self.main_path}, aborting"
            )

        redirections_to_ignore = set()

        logger.debug(f"Preparing {len(self.redirections)} redirections")
        for redirect_source, redirect_target in self.redirections.items():

            # if the redirect source has already been detected as a thing to ignore,
            # simply continue
            if redirect_source in redirections_to_ignore:
                continue

            # if the URL is already expected, then just ignore the redirection
            if redirect_source in self.expected_zim_items:
                redirections_to_ignore.add(redirect_source)
                continue

            final_redirect_target = redirect_target
            # accumulator to detect nested redirection loops
            redirection_items = [redirect_source]
            # process redirection iteratively since the target of the redirection
            # might be a redirection itself
            while (
                final_redirect_target in self.redirections
                and final_redirect_target not in redirection_items
                and final_redirect_target not in self.expected_zim_items
            ):
                # If redirection target is identical, we have finished looping
                # This should not happen here / be handled upper-level, but it is better
                # to check than finishing in a dead loop
                if final_redirect_target == self.redirections[final_redirect_target]:
                    logger.warning(
                        f"Redirection to self found for {final_redirect_target.value}"
                    )
                    break
                redirection_items.append(final_redirect_target)
                final_redirect_target = self.redirections[final_redirect_target]

            if final_redirect_target in redirection_items:
                # If the redirect target is the source ... we obviously have an issue
                logger.warning(
                    f"Redirection loop found for {redirect_source.value}, corresponding"
                    " ZIMPaths will be ignored."
                )
                for item in redirection_items:
                    logger.warning(
                        f"  - {item.value} redirects to {self.redirections[item].value}"
                    )
                    redirections_to_ignore.add(item)
            elif final_redirect_target in self.expected_zim_items:
                # if final redirection target is including inside the ZIM, simply add
                # the redirection source to the list of expected ZIM items so that URLs
                # are properly rewritten
                self.expected_zim_items.add(redirect_source)
            else:
                # otherwise add it to a temporary list of items that will have to be
                # dropped from the list of redirections to create
                logger.warning(
                    f"Redirection target of {redirect_source.value} is missing "
                    f"({final_redirect_target.value} is not expected in the ZIM)"
                )
                redirections_to_ignore.add(redirect_source)

        logger.debug(f"{len(redirections_to_ignore)} redirections will be ignored")

        # update the list of redirections to create
        for redirect_source in redirections_to_ignore:
            self.redirections.pop(redirect_source)

        logger.info(
            f"Expecting {len(self.expected_zim_items)} ZIM entries including redirects"
        )

    def find_icon_and_language(self, record, content):
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
                icon_url = icon.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                    "href"
                ]
            else:
                icon_url = "/favicon.ico"

            # transform icon URL into WARC path
            self.favicon_path = normalize(
                HttpUrl(
                    urljoin(
                        get_record_url(record),
                        icon_url,
                    )
                )
            )

        if not self.language:
            # HTML5 Standard
            lang_elem = soup.find("html", attrs={"lang": True})
            if lang_elem:
                self.language = parse_language(
                    lang_elem.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                        "lang"
                    ]
                )
                return

            # W3C recommendation
            lang_elem = soup.find(
                "meta", {"http-equiv": "content-language", "content": True}
            )
            if lang_elem:
                self.language = parse_language(
                    lang_elem.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                        "content"
                    ]
                )
                return

            # SEO Recommendations
            lang_elem = soup.find("meta", {"name": "language", "content": True})
            if lang_elem:
                self.language = parse_language(
                    lang_elem.attrs[  # pyright: ignore[reportGeneralTypeIssues ,reportAttributeAccessIssue]
                        "content"
                    ]
                )
                return

    def retrieve_illustration(self):
        """sets self.illustration either from WARC or download

        Uses fallback in case of errors/missing"""

        if self.favicon_url or self.favicon_path:
            # look into WARC records
            for record in iter_warc_records(self.inputs):
                if record.rec_type != "response":
                    continue
                url = get_record_url(record)
                path = normalize(HttpUrl(url))
                if path == self.favicon_path or url == self.favicon_url:
                    logger.debug("Found WARC record for favicon")
                    if (
                        record.http_headers
                        and record.http_headers.get_statuscode() != "200"
                    ):  # pragma: no cover
                        logger.warning("WARC record for favicon is unusable")
                        break
                    self.illustration = get_record_content(record)
                    break

            # download favicon_url (might be custom URL, not present in WARC records)
            if not self.illustration and self.favicon_url:
                try:
                    dst = io.BytesIO()
                    if not stream_file(self.favicon_url, byte_stream=dst)[0]:
                        raise OSError(
                            "No bytes received downloading favicon"
                        )  # pragma: no cover
                    self.illustration = dst.getvalue()
                except Exception as exc:
                    logger.warning("Unable to download favicon", exc_info=exc)

        if not self.illustration:
            logger.warning("Illustration not found, using default")
            self.illustration = DEFAULT_DEV_ZIM_METADATA["Illustration_48x48_at_1"]

        # Illustration is now set, no need to keep url/path anymore
        del self.favicon_url
        del self.favicon_path

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
        location = urljoin(url, location)
        return normalize(HttpUrl(url)) == normalize(HttpUrl(location))

    def add_items_for_warc_record(self, record):

        if record.rec_type not in ("response", "revisit"):
            return

        url = get_record_url(record)
        if not url:
            logger.debug(f"Skipping record with empty WARC-Target-URI {record}")
            return

        item_zim_path = normalize(HttpUrl(url))

        # if include_domains is set, only include urls from those domains
        if self.include_domains:
            parts = urlsplit(url)
            if not any(
                parts.netloc.endswith(domain) for domain in self.include_domains
            ):
                logger.debug(f"Skipping url {url}, outside included domains")
                return

        if item_zim_path in self.added_zim_items:
            logger.debug(f"Skipping duplicate {url}, already added to ZIM")
            return

        if record.rec_type == "response":
            status_code = get_status_code(record)
            if not isinstance(status_code, HTTPStatus):
                logger.warning(
                    f"Skipping record with unexpected HTTP return code {status_code} "
                    f"{item_zim_path}"
                )
                return

            if not can_process_status_code(status_code):
                logger.debug(
                    f"Skipping record with unprocessable HTTP return code {status_code}"
                    f" {item_zim_path}"
                )
                return

            if status_code_is_processable_redirect(status_code):
                # no log, we will process it afterwards
                return

            if self.is_self_redirect(record, url):
                logger.debug("Skipping self-redirect: " + url)
                return

            payload_item = WARCPayloadItem(
                item_zim_path,
                record,
                self.pre_head_template,
                self.post_head_template,
                self.expected_zim_items,
                self.missing_zim_paths,
                self.js_modules,
            )

            if len(payload_item.content) != 0:
                try:
                    self.creator.add_item(payload_item)
                except RuntimeError as exc:
                    if not DUPLICATE_EXC_STR.match(str(exc)):
                        raise exc
                self.total_records += 1
                self.update_stats()

            self.added_zim_items.add(item_zim_path)

        elif (
            record.rec_type == "revisit"
            and record.rec_headers["WARC-Refers-To-Target-URI"] != url
            and item_zim_path not in self.revisits
        ):  # pragma: no branch
            self.revisits[item_zim_path] = normalize(
                HttpUrl(record.rec_headers["WARC-Refers-To-Target-URI"])
            )


def iter_warc_records(inputs):
    """iter warc records, including appending request data to matching response"""
    for filename in iter_file_or_dir(inputs):
        with open(filename, "rb") as fh:
            for record in buffering_record_iter(ArchiveIterator(fh), post_append=True):
                if record and record.rec_type in ("resource", "response", "revisit"):
                    yield record
