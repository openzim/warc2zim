from collections.abc import Iterable
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from warc2zim.constants import logger

ZIM_ILLUSTRATION_SIZE = 48


@dataclass(frozen=True)
class IconUrlAndSize:
    """Helper class to compare icons for warc2zim usage"""

    url: str
    width: int | None
    height: int | None

    def __lt__(self, other):
        return IconUrlAndSize._cmp_icons(self, other) < 0

    def __gt__(self, other):
        return IconUrlAndSize._cmp_icons(self, other) > 0

    @classmethod
    def _cmp_icons(cls, x: "IconUrlAndSize", y: "IconUrlAndSize") -> int:
        if x.width and y.width and x.height and y.height:
            # icons are supposed to be squared ; should they not be squared, we consider
            # only the smallest dimension for comparison
            x_dim = min(x.width, x.height)
            y_dim = min(y.width, y.height)
            if x_dim == ZIM_ILLUSTRATION_SIZE:
                if y_dim != ZIM_ILLUSTRATION_SIZE:
                    return 1  # x is perfect, y not
                return 0  # both images are perfect
            if x_dim > ZIM_ILLUSTRATION_SIZE:
                if y_dim == ZIM_ILLUSTRATION_SIZE:
                    return -1  # y is perfect, x not
                elif x_dim < y_dim:
                    return -1  # perfer biggest icon (y)
                elif x_dim == y_dim:
                    return 0  # both icon are equivalent
                else:
                    return 1  #  perfer biggest icon (x)
            if y_dim >= ZIM_ILLUSTRATION_SIZE:  # and x < ZIM_ILLUSTRATION_SIZE
                return -1  # prefer biggest icon (y)
            elif (
                x_dim < y_dim
            ):  #  and x < ZIM_ILLUSTRATION_SIZE and y < ZIM_ILLUSTRATION_SIZE
                return -1  # prefer biggest icon (y)
            elif (
                x_dim == y_dim
            ):  #  and x < ZIM_ILLUSTRATION_SIZE and y < ZIM_ILLUSTRATION_SIZE
                return 0  # both are too small
            else:
                return 1  # prefer biggest icon (x)
        elif x.width and x.height and not y.width:
            x_dim = min(x.width, x.height)
            if x_dim >= ZIM_ILLUSTRATION_SIZE and x_dim >= ZIM_ILLUSTRATION_SIZE:
                return 1  # prefer x which is known to be big enough
            else:
                return 0  # x has height but it is too small, y we don't know
        elif not x.width and y.width and y.height:
            y_dim = min(y.width, y.height)
            if y_dim >= ZIM_ILLUSTRATION_SIZE and y_dim >= ZIM_ILLUSTRATION_SIZE:
                return -1  # prefer y which is known to be big enough
            else:
                return 0  # y has height but it is too small, x we don't know
        else:  # all other cases where we miss some sizes in x and y
            return 0


def sort_icons(icons: Iterable[IconUrlAndSize]) -> list[IconUrlAndSize]:
    """Sort icons by order of preference for warc2zim usage"""
    return sorted(icons, reverse=True)


def find_and_sort_icons(content: str | bytes) -> list[str]:
    """Given some HTML content, get the sorted list of icons URL

    Builds a list of all icons URLs found in <link rel="icon">.

    The list is sorted by fit for warczim usage:
    - prefer a ZIM_ILLUSTRATION_SIZExZIM_ILLUSTRATION_SIZE icon if it exists
    - prefer biggest icon otherwise

    The whole sorted list is needed because scraper does not know in advance what will
    be present inside the WARC.

    We consider only rel="icon" links because others are never loaded by the crawler
    (including the rel="apple-touch-icon" links even when an apple device is passed,
    since we still use brave browser + these icons are mostly used for bookmarks).
    """

    icons_with_data: list[IconUrlAndSize] = []

    soup = BeautifulSoup(content, "html.parser")

    icon_tags = soup.find_all("link", rel="icon")
    for icon_tag in icon_tags:
        if not (icon_tag and isinstance(icon_tag, Tag) and icon_tag.attrs.get("href")):
            continue

        href = icon_tag.attrs["href"]
        width = None
        height = None
        if icon_tag.attrs.get("sizes"):
            try:
                size_items = icon_tag.attrs["sizes"].split("x")
                if len(size_items) == 2:  # noqa: PLR2004
                    width = int(size_items[0])
                    height = int(size_items[1])
            except Exception as exc:
                logger.warning(
                    "Failed to convert sizes into int values (will be considered"
                    f' missing): href: {href}, sizes: {icon_tag.attrs["sizes"]}',
                    exc_info=exc,
                )

        # Let's assume size is 16x16 for favicons
        if (not width or not height) and "favicon.ico" in href:
            width = 16
            height = 16

        icons_with_data.append(IconUrlAndSize(url=href, width=width, height=height))

    # sort icons found and deduplicate URLs while keeping sort order
    icons_urls: list[str] = []
    for icon in sort_icons(icons_with_data):
        if icon.url not in icons_urls:
            icons_urls.append(icon.url)
    return icons_urls
