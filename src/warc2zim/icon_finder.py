import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag
from zimscraperlib.rewriting.url_rewriting import HttpUrl

from warc2zim.constants import logger

ZIM_ILLUSTRATION_SIZE = 48


@dataclass(frozen=True)
class Icon:
    """Helper class to compare icons for warc2zim usage"""

    url: str
    width: int
    height: int
    icon: bytes
    format: str | None

    def __lt__(self, other):
        return Icon._cmp_icons(self, other) < 0

    def __gt__(self, other):
        return Icon._cmp_icons(self, other) > 0

    @classmethod
    def _cmp_icons(cls, a: Icon, b: Icon) -> int:
        # icons are supposed to be squared ; should they not be squared, we consider
        # only the smallest dimension for comparison
        a_min = min(a.width, a.height)
        b_min = min(b.width, b.height)
        if a_min == ZIM_ILLUSTRATION_SIZE:
            if b_min != ZIM_ILLUSTRATION_SIZE:
                return 1  # a_min is perfect, b_min not
            return 0  # both images are perfect
        if a_min > ZIM_ILLUSTRATION_SIZE:
            if b_min == ZIM_ILLUSTRATION_SIZE:
                return -1  # b_min is perfect, a_min not
            elif a_min < b_min:
                return -1  # prefer biggest icon (b)
            elif a_min == b_min:
                return 0  # both icon are equivalent
            else:
                return 1  #  perfer biggest icon (a)
        if b_min >= ZIM_ILLUSTRATION_SIZE:  # a_min is < ZIM_ILLUSTRATION_SIZE
            return -1  # prefer biggest icon (b)
        elif a_min < b_min:  #  a_min and b_min are < ZIM_ILLUSTRATION_SIZE
            return -1  # prefer biggest icon (b)
        elif a_min == b_min:  # a_min and b_min are < ZIM_ILLUSTRATION_SIZE
            return 0  # both are too small
        else:
            return 1  # prefer biggest icon (a)


def get_sorted_icons(icons: Iterable[Icon]) -> list[Icon]:
    """Returns a sorted icons list, by order of preference for warc2zim usage"""
    return sorted(icons, reverse=True)


def icons_in_html(content: str | bytes) -> set[str]:
    """Given some HTML content, get the sorted list of icons URL

    Builds a list of all icons URLs found in <link rel="icon">.

    The whole sorted list is needed because scraper does not know in advance what will
    be present inside the WARC / downloadable / has the best size fit.

    We consider only rel="icon" links because others are never loaded by the crawler
    (including the rel="apple-touch-icon" links even when an apple device is passed,
    since we still use brave browser + these icons are mostly used for bookmarks).
    """

    soup = BeautifulSoup(content, "html.parser")

    icon_tags = soup.find_all("link", rel="icon")

    return {
        str(icon_tag.attrs["href"])
        for icon_tag in icon_tags
        if icon_tag and isinstance(icon_tag, Tag) and "href" in icon_tag.attrs
    }


def _normalized(url: str) -> str | None:
    """Normalize a URL for matching crawler metadata entries."""
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            return None

        scheme = parsed.scheme.lower()
        hostname = parsed.hostname.lower()
        port = parsed.port

        if port == (80 if scheme == "http" else 443):
            port = None

        netloc = f"[{hostname}]" if ":" in hostname else hostname
        if port is not None:
            netloc = f"{netloc}:{port}"

        path = parsed.path or "/"
        if path != "/":
            path = path.rstrip("/")

        return urlunsplit((scheme, netloc, path, parsed.query, ""))
    except AttributeError, TypeError, ValueError:
        return None


def _parse_pages_entry(line: str) -> tuple[str, HttpUrl, bool] | None:
    """Extract (url, favicon_url, is_seed) from a valid pages.jsonl line."""
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict):
        return None

    raw_url = entry.get("url")
    raw_favicon = entry.get("favicon")
    if not isinstance(raw_url, str) or not isinstance(raw_favicon, str):
        return None
    raw_favicon = raw_favicon.strip()
    if not raw_url or not raw_favicon:
        return None

    favicon = urljoin(raw_url, raw_favicon)
    try:
        favicon_url = HttpUrl(favicon)
    except ValueError:
        return None

    return raw_url, favicon_url, entry.get("seed") is True


def favicon_from_pages_jsonl(
    pages_jsonl_path: Path | str,
    page_url: HttpUrl | None = None,
) -> HttpUrl | None:
    """Return a matching favicon URL, falling back to the seed or first entry."""
    path = Path(pages_jsonl_path)
    target_norm = _normalized(page_url.value) if page_url else None
    seed_favicon: HttpUrl | None = None
    first_favicon: HttpUrl | None = None

    try:
        with path.open(encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                parsed = _parse_pages_entry(line)
                if not parsed:
                    continue
                raw_url, favicon_url, is_seed = parsed
                if target_norm is not None and _normalized(raw_url) == target_norm:
                    return favicon_url
                if is_seed and seed_favicon is None:
                    seed_favicon = favicon_url
                if first_favicon is None:
                    first_favicon = favicon_url
    except (OSError, UnicodeDecodeError) as exc:
        logger.debug(f"Failed to read pages.jsonl from {path}: {exc}")
        return None

    if seed_favicon:
        return seed_favicon
    return first_favicon if not page_url else None
