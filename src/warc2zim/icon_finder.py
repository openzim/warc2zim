from collections.abc import Iterable
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

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
    def _cmp_icons(cls, a: "Icon", b: "Icon") -> int:
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
