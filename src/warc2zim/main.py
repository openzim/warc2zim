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

import sys
import logging
from argparse import ArgumentParser

from warc2zim.converter import Converter, get_version

# Shared logger
logger = logging.getLogger("warc2zim")


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
    converter = Converter(r)
    return converter.run()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(warc2zim())
