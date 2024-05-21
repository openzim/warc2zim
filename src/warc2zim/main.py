#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

import sys
from argparse import ArgumentParser

from warc2zim.converter import Converter
from warc2zim.utils import get_version


def main(raw_args=None):
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
        "--tags",
        help="List of ZIM Tags, single string with individual tags separated by a "
        "semicolon.",
        default="",
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

    parser.add_argument(
        "--scraper-suffix",
        help="Additional string to append as a suffix to ZIM Scraper metadata, in "
        "addition to regular warc2zim value",
    )

    parser.add_argument(
        "--continue-on-error",
        help="Dev feature: do not stop on WARC record processing issue, continue with "
        "next record",
        action="store_true",
    )

    parser.add_argument(
        "--failed-items",
        help="Directory where failed item(s) will be stored. Either absolute path or "
        "relative to output directory",
        default="fails",
    )

    parser.add_argument(
        "--disable-metadata-checks",
        help="Disable validity checks of metadata according to openZIM conventions",
        action="store_true",
        default=False,
        dest="disable_metadata_checks",
    )

    args = parser.parse_args(args=raw_args)
    converter = Converter(args)
    return converter.run()


if __name__ == "__main__":
    sys.exit(main())
