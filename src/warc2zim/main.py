#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim conversion utility

This utility provides a conversion from WARC records to ZIM files.
The WARCs are converted in a 'lossless' way, no data from WARC records is lost.
Each WARC record results in two ZIM articles:
- The WARC payload is stored under /A/<url>
- The WARC headers + HTTP headers are stored under the /H/<url>

Given a WARC response record for 'https://example.com/', two ZIM articles are created /A/example.com/ and /H/example.com/ are created.

Only WARC response and resource records are stored.

If the WARC contains multiple entries for the same URL, only the first entry is added, and later entries are ignored. A warning is printed as well.

"""

import os
import logging
import mimetypes
import sys
from argparse import ArgumentParser
from urllib.parse import urlsplit, urljoin

import pkg_resources
import requests
from warcio import ArchiveIterator
from libzim.writer import Article, Blob
from zimscraperlib.zim.creator import Creator
from bs4 import BeautifulSoup


# Shared logger
logger = logging.getLogger("warc2zim")

# HTML mime types
HTML_TYPES = ("text/html", "application/xhtml", "application/xhtml+xml")


# ============================================================================
class BaseArticle(Article):
    """ BaseArticle for all ZIM Articles in warc2zim with default settings
    """

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
    """ WARCHeadersArticle used to store the WARC + HTTP headers as text
    Usually stored under H namespace
    """

    def __init__(self, record):
        super().__init__()
        self.record = record
        self.url = record.rec_headers.get("WARC-Target-URI")

    def get_url(self):
        return "H/" + canonicalize(self.url)

    def get_title(self):
        return self.url

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
    """ WARCPayloadArticle used to store the WARC payload
    Usually stored under A namespace
    """

    def __init__(self, record):
        super().__init__()
        self.record = record
        self.url = record.rec_headers.get("WARC-Target-URI")
        self.mime = get_record_mime_type(record)
        self.title = self.url
        self.payload = self.record.content_stream().read()

        # converting text/html to application/octet-stream to avoid rewriting by kiwix
        # original mime type still preserved in the headers block
        if self.mime == "text/html":
            self.mime = "application/octet-stream"
            self.title = parse_title(self.payload)

    def get_url(self):
        return "A/" + canonicalize(self.url)

    def get_title(self):
        return self.title

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        return Blob(self.payload)

    def should_index(self):
        return True


# ============================================================================
class RWPRemoteArticle(BaseArticle):
    def __init__(self, prefix, filename):
        super().__init__()
        self.prefix = prefix
        self.filename = filename

        try:
            resp = requests.get(self.prefix + filename)
            self.content = resp.content
            self.mime = resp.headers.get("Content-Type").split(";")[0]
        except Exception as e:
            logger.error(e)
            logger.error(
                "Unable to load replay system file: {0}".format(self.prefix + filename)
            )
            raise

    def get_url(self):
        return "A/" + self.filename

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        return Blob(self.content)


# ============================================================================
class RWPStaticArticle(BaseArticle):
    def __init__(self, filename, main_url):
        super().__init__()
        self.filename = filename
        self.main_url = main_url

        self.mime, _ = mimetypes.guess_type(filename)
        self.mime = self.mime or "application/octet-stream"
        self.content = pkg_resources.resource_string(
            "warc2zim", "replay/" + filename
        ).decode("utf-8")

    def get_url(self):
        return "A/" + self.filename

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        if self.mime == "text/html":
            content = self.content.replace("$MAIN_URL", self.main_url)
        else:
            content = self.content
        return Blob(content.encode("utf-8"))


# ============================================================================
class FaviconArticle(BaseArticle):
    def __init__(self, favicon_url):
        super().__init__()
        self.favicon_url = favicon_url

    def get_url(self):
        return "-/favicon"

    def is_redirect(self):
        return True

    def get_redirect_url(self):
        return "A/" + canonicalize(self.favicon_url)


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
        if not self.output:
            self.output, ext = os.path.splitext(args.inputs[0])
            self.output += ".zim"

        self.inputs = args.inputs
        self.replay_viewer_source = args.replay_viewer_source

        self.main_url = args.url
        self.include_all = args.include_all
        self.include_domains = args.include_domains
        if self.main_url:
            if not self.include_all and not self.include_domains:
                self.include_domains = [urlsplit(self.main_url).netloc]

        self.date = None  # date is loaded from date of main page in WARC

        self.favicon_url = args.favicon
        self.language = args.lang
        self.title = args.title

        self.metadata = {
            "name": args.name,
            "description": args.desc,
            "creator": args.creator,
            "publisher": args.publisher,
            "tags": ";".join(args.tags) or None,
            # optional
            "source": args.source,
            "flavour": "",
            "scraper": "warc2zim " + get_version(),
        }

        self.replay_articles = []
        self.revisits = {}

    def add_remote_or_local(self, filename):
        if self.replay_viewer_source:
            article = RWPRemoteArticle(self.replay_viewer_source, filename)
        else:
            article = RWPStaticArticle(filename, self.main_url)

        self.replay_articles.append(article)

    def run(self):
        self.find_main_page_metadata()

        self.add_remote_or_local("sw.js")

        for filename in pkg_resources.resource_listdir("warc2zim", "replay"):
            if filename != "sw.js":
                self.replay_articles.append(RWPStaticArticle(filename, self.main_url))

        with Creator(
            self.output,
            main_page="index.html",
            language=self.language or "eng",
            title=self.title,
            date=self.date or datetime.date.today(),
            **self.metadata
        ) as zimcreator:
            # zimcreator.update_metadata(**self.metadata)

            for article in self.generate_all_articles():
                if article:
                    zimcreator.add_zim_article(article)

    def iter_warc_records(self):
        for warcfile in self.inputs:
            with open(warcfile, "rb") as warc_fh:
                for record in ArchiveIterator(warc_fh):
                    if record.rec_type not in ("resource", "response", "revisit"):
                        continue

                    yield record

    def find_main_page_metadata(self):
        for record in self.iter_warc_records():
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
                if not self.include_all and not self.include_domains:
                    self.include_domains = [urlsplit(self.main_url).netloc]

            if self.main_url != url:
                continue

            # if we get here, found record for the main page

            # if main page is not html, still allow (eg. could be text, img), but print warning
            if mime not in HTML_TYPES:
                logger.warning(
                    "Main page is not an HTML Page, mime type is: {0} - Skipping Favicon and Language detection".format(
                        mime
                    )
                )

            self.date = record.rec_headers["WARC-Date"]
            content = record.content_stream().read()

            if not self.title:
                self.title = parse_title(content)

            # only attempt to parse if not explicitly set
            if not self.favicon_url or not self.language:
                self.find_icon_and_language(content)

            logger.debug("Date: {0}".format(self.date))
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
        if self.favicon_url:
            yield FaviconArticle(self.favicon_url)

        # add replay system
        for article in self.replay_articles:
            yield article

        for record in self.iter_warc_records():
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

    def articles_for_warc_record(self, record):
        url = record.rec_headers["WARC-Target-URI"]
        if url in self.indexed_urls:
            logger.warning("Skipping duplicate {0}, already added to ZIM".format(url))
            return

        # if not include_all, only include urls from main_url domain or subdomain
        if not self.include_all:
            parts = urlsplit(url)
            if not any(
                parts.netloc.endswith(domain) for domain in self.include_domains
            ):
                logger.debug("Skipping url {0}, outside included domains".format(url))
                return

        if record.rec_type != "revisit":
            yield WARCHeadersArticle(record)
            payload_article = WARCPayloadArticle(record)

            if len(payload_article.payload) != 0:
                yield payload_article

            self.indexed_urls.add(url)

        elif (
            record.rec_headers["WARC-Refers-To-Target-URI"] != url
            and url not in self.revisits
        ):
            self.revisits[url] = record


# ============================================================================
def get_record_mime_type(record):
    if record.http_headers:
        # if the record has HTTP headers, use the Content-Type from those (eg. 'response' record)
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
def warc2zim(args=None):
    parser = ArgumentParser(description="Create ZIM files from WARC files")

    parser.add_argument("-V", "--version", action="version", version=get_version())
    parser.add_argument("-v", "--verbose", action="store_true")

    parser.add_argument(
        "inputs",
        nargs="+",
        help="""Paths of directories and/or files to be included in
                                the WARC file.""",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="""Output filename for ZIM file (.zim extension will be added)""",
        metavar="output",
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
        "-a",
        "--include-all",
        action="store_true",
        help="If set, include all URLs in ZIM, not just those specified in --include-domains",
    )

    parser.add_argument(
        "-i",
        "--include-domains",
        action="append",
        help="List of domains that should be included. Not used if --include-all is set. Defaults to domain of the main url",
    )

    parser.add_argument("-f", "--favicon", help="Favicon for Main Page")

    # optional metadata
    parser.add_argument("--name", help="The name of the ZIM", default="")
    parser.add_argument("--title", help="The Title", default="")
    parser.add_argument("--desc", help="The Description", default="")
    parser.add_argument("--tags", action="append", help="One or more tags", default=[])
    parser.add_argument(
        "--lang",
        help="Language (should be a ISO-639-3 language code). If unspecified, will attempt to detect from main page, or use 'eng'",
        default="",
    )
    parser.add_argument("--publisher", help="ZIM publisher", default="-")
    parser.add_argument("--creator", help="ZIM creator", default="-")
    parser.add_argument("--source", help="ZIM source", default="")

    r = parser.parse_args(args=args)
    warc2zim = WARC2Zim(r)
    return warc2zim.run()


# ============================================================================
def canonicalize(url):
    """ Return a 'canonical' version of the url under which it is stored in the ZIM
    For now, just removing the scheme
    """
    return url.split("//", 2)[1]


# ============================================================================
def get_version():
    return pkg_resources.get_distribution("warc2zim").version


# ============================================================================
if __name__ == "__main__":  # pragma: no cover
    warc2zim()
