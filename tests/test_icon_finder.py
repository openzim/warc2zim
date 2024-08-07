from pathlib import Path

import pytest

from warc2zim.icon_finder import Icon, get_sorted_icons, icons_in_html


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
