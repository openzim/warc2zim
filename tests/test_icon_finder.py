import json
from pathlib import Path

import pytest
from zimscraperlib.rewriting.url_rewriting import HttpUrl

from warc2zim.icon_finder import (
    Icon,
    _normalized,
    favicon_from_pages_jsonl,
    get_sorted_icons,
    icons_in_html,
)


@pytest.mark.parametrize(
    "html, expected",
    [
        pytest.param(
            """<link rel="foo" href="https://somewhere/favicon.ico">""",
            set(),
            id="other_rel",
        ),
        pytest.param(
            """<link rel="icon" href="https://somewhere/favicon.ico">""",
            {"https://somewhere/favicon.ico"},
            id="simple_icon",
        ),
        pytest.param(
            """<link rel="icon" href="https://somewhere/favicon.ico">""",
            {"https://somewhere/favicon.ico"},
            id="simple_icon",
        ),
        pytest.param(
            """<link rel="icon">""",
            set(),
            id="icon_href_missing",
        ),
        pytest.param(
            """<link rel="shortcut icon" href="https://somewhere/favicon.ico">""",
            {"https://somewhere/favicon.ico"},
            id="simple_shortcut_icon",
        ),
        pytest.param(
            """<link rel="icon" sizes="48x48" href="https://somewhere/favicon.ico">
            <link rel="icon" sizes="96x96" href="https://somewhere/favicon.ico">""",
            {"https://somewhere/favicon.ico"},
            id="no_duplicates",
        ),
        pytest.param(
            """<link rel="icon" sizes="96x96" href="https://somewhere/favicon1.ico">
            <link rel="icon" sizes="48x48" href="https://somewhere/favicon2.ico">""",
            {"https://somewhere/favicon2.ico", "https://somewhere/favicon1.ico"},
            id="sort_by_size",
        ),
        pytest.param(
            Path("tests/data-special/icons.html").read_text(),
            {
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/android-chrome-192x192.png",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon-96x96.png",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon-32x32.png",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon.ico",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon-16x16.png",
            },
            id="real_life",
        ),
        pytest.param(
            """<link rel="shortcut icon" sizes="aaxbb" href="https://somewhere/favicon.ico">""",
            {"https://somewhere/favicon.ico"},
            id="bad_sizes_1",
        ),
        pytest.param(
            """<link rel="shortcut icon" sizes="12x12x12" href="https://somewhere/favicon.ico">""",
            {"https://somewhere/favicon.ico"},
            id="bad_sizes_2",
        ),
    ],
)
def test_icons_in_html(html, expected):
    assert icons_in_html(html) == expected


@pytest.mark.parametrize(
    "unsorted, expected",
    [
        pytest.param([], [], id="empty"),
        pytest.param(
            [Icon("url1", 12, 12, b"", None)],
            [Icon("url1", 12, 12, b"", None)],
            id="one_item",
        ),
        pytest.param(
            [Icon("url3", 12, 12, b"", None), Icon("url2", 96, 96, b"", None)],
            [Icon("url2", 96, 96, b"", None), Icon("url3", 12, 12, b"", None)],
            id="two_items_with_size1",
        ),
        pytest.param(
            [Icon("url3", 128, 128, b"", None), Icon("url2", 96, 96, b"", None)],
            [Icon("url3", 128, 128, b"", None), Icon("url2", 96, 96, b"", None)],
            id="two_items_with_size2",
        ),
        pytest.param(
            [Icon("url2", 96, 96, b"", None), Icon("url3", 128, 128, b"", None)],
            [Icon("url3", 128, 128, b"", None), Icon("url2", 96, 96, b"", None)],
            id="two_items_with_size3",
        ),
        pytest.param(
            [Icon("url3", 12, 12, b"", None), Icon("url2", 26, 26, b"", None)],
            [Icon("url2", 26, 26, b"", None), Icon("url3", 12, 12, b"", None)],
            id="two_items_with_size4",
        ),
        pytest.param(
            [Icon("url2", 26, 26, b"", None), Icon("url3", 12, 12, b"", None)],
            [Icon("url2", 26, 26, b"", None), Icon("url3", 12, 12, b"", None)],
            id="two_items_with_size5",
        ),
        pytest.param(
            [Icon("url2", 48, 48, b"", None), Icon("url3", 12, 12, b"", None)],
            [Icon("url2", 48, 48, b"", None), Icon("url3", 12, 12, b"", None)],
            id="two_items_with_size6",
        ),
        pytest.param(
            [Icon("url2", 48, 48, b"", None), Icon("url3", 96, 96, b"", None)],
            [Icon("url2", 48, 48, b"", None), Icon("url3", 96, 96, b"", None)],
            id="two_items_with_size7",
        ),
        pytest.param(
            [Icon("url3", 12, 12, b"", None), Icon("url2", 48, 48, b"", None)],
            [Icon("url2", 48, 48, b"", None), Icon("url3", 12, 12, b"", None)],
            id="two_items_with_size8",
        ),
        pytest.param(
            [Icon("url3", 96, 96, b"", None), Icon("url2", 48, 48, b"", None)],
            [Icon("url2", 48, 48, b"", None), Icon("url3", 96, 96, b"", None)],
            id="two_items_with_size9",
        ),
        pytest.param(
            [Icon("url2", 48, 48, b"", None), Icon("url3", 48, 48, b"", None)],
            [Icon("url2", 48, 48, b"", None), Icon("url3", 48, 48, b"", None)],
            id="two_items_with_size10",
        ),
        pytest.param(
            [Icon("url2", 96, 96, b"", None), Icon("url3", 96, 96, b"", None)],
            [Icon("url2", 96, 96, b"", None), Icon("url3", 96, 96, b"", None)],
            id="two_items_with_size11",
        ),
        pytest.param(
            [Icon("url3", 32, 32, b"", None), Icon("url2", 96, 96, b"", None)],
            [Icon("url2", 96, 96, b"", None), Icon("url3", 32, 32, b"", None)],
            id="two_items_with_size12",
        ),
        pytest.param(
            [Icon("url2", 96, 96, b"", None), Icon("url3", 32, 32, b"", None)],
            [Icon("url2", 96, 96, b"", None), Icon("url3", 32, 32, b"", None)],
            id="two_items_with_size13",
        ),
        pytest.param(
            [Icon("url2", 26, 26, b"", None), Icon("url3", 26, 26, b"", None)],
            [Icon("url2", 26, 26, b"", None), Icon("url3", 26, 26, b"", None)],
            id="two_items_with_size14",
        ),
    ],
)
def test_get_sorted_icons(unsorted, expected):
    assert get_sorted_icons(unsorted) == expected
    if len(unsorted) == 2:
        if unsorted[0] == expected[1]:
            assert unsorted[0] < unsorted[1]
            assert unsorted[1] > unsorted[0]


def _write_pages(tmp_path: Path, lines: list) -> Path:
    pages_file = tmp_path / "pages.jsonl"
    pages_file.write_text(
        "\n".join(line if isinstance(line, str) else json.dumps(line) for line in lines)
        + "\n",
        encoding="utf-8",
    )
    return pages_file


def test_favicon_from_pages_jsonl_matching_target(tmp_path):
    pages_file = _write_pages(
        tmp_path,
        [
            {"format": "json-pages-1.0", "id": "pages"},
            {"url": "https://example.com/", "seed": True, "favicon": "/favicon.ico"},
            {
                "url": "https://example.com/other",
                "seed": False,
                "favicon": "https://example.com/other.png",
            },
        ],
    )
    root_icon = HttpUrl("https://example.com/favicon.ico")
    assert (
        favicon_from_pages_jsonl(pages_file, HttpUrl("https://example.com/"))
        == root_icon
    )
    assert (
        favicon_from_pages_jsonl(pages_file, HttpUrl("https://example.com"))
        == root_icon
    )
    assert favicon_from_pages_jsonl(
        pages_file, HttpUrl("https://example.com/other")
    ) == HttpUrl("https://example.com/other.png")
    assert (
        favicon_from_pages_jsonl(pages_file, HttpUrl("https://example.com/nope"))
        == root_icon
    )


def test_favicon_from_pages_jsonl_seed_not_subpage(tmp_path):
    pages_file = _write_pages(
        tmp_path,
        [
            {"url": "https://example.com/sub", "seed": False, "favicon": "/sub.ico"},
            {"url": "https://example.com/", "seed": True, "favicon": "/seed.ico"},
        ],
    )
    seed_icon = HttpUrl("https://example.com/seed.ico")
    assert (
        favicon_from_pages_jsonl(pages_file, HttpUrl("https://example.com/"))
        == seed_icon
    )
    assert (
        favicon_from_pages_jsonl(pages_file, HttpUrl("https://other.com/")) == seed_icon
    )


def test_favicon_from_pages_jsonl_relative_paths(tmp_path):
    pages_file = _write_pages(
        tmp_path,
        [
            {
                "url": "https://example.com/sub/page.html",
                "seed": True,
                "favicon": "../assets/icon.png",
            }
        ],
    )
    assert favicon_from_pages_jsonl(
        pages_file, HttpUrl("https://example.com/sub/page.html")
    ) == HttpUrl("https://example.com/assets/icon.png")


def test_favicon_from_pages_jsonl_first_entry_fallback(tmp_path):
    pages_file = _write_pages(
        tmp_path,
        [
            {"url": "https://example.com/p1", "seed": False, "favicon": "/1.ico"},
            {"url": "https://example.com/p2", "seed": False, "favicon": "/2.ico"},
        ],
    )
    assert favicon_from_pages_jsonl(pages_file) == HttpUrl("https://example.com/1.ico")
    assert favicon_from_pages_jsonl(pages_file, HttpUrl("https://unknown.com")) is None


def test_favicon_from_pages_jsonl_missing_file(tmp_path):
    assert favicon_from_pages_jsonl(tmp_path / "non_existent.jsonl") is None


def test_favicon_from_pages_jsonl_malformed_and_empty(tmp_path):
    pages_file = _write_pages(
        tmp_path,
        [
            "",
            "{malformed json",
            {"url": "https://example.com/no-fav"},
            {"url": "https://example.com/empty-fav", "favicon": "  "},
            {"url": "https://example.com/null-fav", "favicon": None},
            {"url": "https://example.com/data", "favicon": "data:image/png;base64,1"},
            {"url": "https://example.com/valid", "favicon": "/valid.ico"},
        ],
    )
    assert favicon_from_pages_jsonl(pages_file) == HttpUrl(
        "https://example.com/valid.ico"
    )


def test_favicon_from_pages_jsonl_no_valid_favicons(tmp_path):
    pages_file = _write_pages(
        tmp_path,
        [
            123,
            ["not", "a", "dict"],
            {"url": 123, "favicon": "/1.ico"},
            {"url": "https://example.com/1", "favicon": None},
            {"url": "https://example.com/2", "favicon": ""},
        ],
    )
    assert favicon_from_pages_jsonl(pages_file) is None


def test_normalized_url_coverage():
    assert _normalized("http://example.com:80/") == "http://example.com/"
    assert _normalized("http://example.com:80") == "http://example.com/"
    assert _normalized("https://example.com:443/test/") == "https://example.com/test"
    assert _normalized("http://example.com:8080/") == "http://example.com:8080/"
    assert _normalized("http://[::1]:8080/") == "http://[::1]:8080/"
    assert _normalized("http://:80/") is None
    assert _normalized("ftp://example.com") is None
    assert _normalized("https://") is None
    assert _normalized("http://example.com:notaport") is None
    assert _normalized(None) is None  # type: ignore[arg-type]
