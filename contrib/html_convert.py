""" html rewrite test utility

This utility takes a given HTML content as input, base64 encoded, its original URL, and
 rewrites its content.

For simplicity, this utility assumes there are no expected ZIM items, so most
URLs will be considered external and hence be kept as-is in the end.

This utility is meant to make debugging of HTML conversion issues easier.

Sample usage:
python contrib/html_convert.py /tmp/content.b64 "https://www.example.com/252653.html"

"""

import base64
import logging
import sys
from pathlib import Path

from warc2zim.constants import logger
from warc2zim.content_rewriting.html import HtmlRewriter
from warc2zim.url_rewriting import ArticleUrlRewriter, HttpUrl, ZimPath
from warc2zim.utils import to_string


def notify(_: ZimPath):
    pass


def main(path_to_b64_content: str, article_url: str, encoding: str | None = None):
    """Run HTML conversion for a given HTML file"""

    # Enable debug logs
    for handler in logger.handlers:
        handler.setLevel(logging.DEBUG)

    b64_content = Path(path_to_b64_content)

    url_rewriter = ArticleUrlRewriter(
        HttpUrl(article_url), existing_zim_paths=set(), missing_zim_paths=set()
    )

    html_rewriter = HtmlRewriter(url_rewriter, "", None, notify)

    content = base64.decodebytes(b64_content.read_bytes())

    output = b64_content.with_suffix(".rewritten.html")

    output.write_text(html_rewriter.rewrite(to_string(content, encoding)).content)

    logger.info(f"Rewritten HTML has been stored in {output}")


if __name__ == "__main__":
    if len(sys.argv) < 3:  # noqa: PLR2004
        logger.error(
            "Incorrect number of arguments\n"
            f"Usage: {sys.argv[0]} <path_to_b64_content> <article_url> [<encoding>]\n"
        )
        sys.exit(1)

    args = sys.argv[1:]
    main(*args)
