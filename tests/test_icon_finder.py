from pathlib import Path

import pytest

from warc2zim.icon_finder import IconUrlAndSize, find_and_sort_icons, sort_icons


@pytest.mark.parametrize(
    "html, expected",
    [
        pytest.param(
            """<link rel="foo" href="https://somewhere/favicon.ico">""",
            [],
            id="other_rel",
        ),
        pytest.param(
            """<link rel="icon" href="https://somewhere/favicon.ico">""",
            ["https://somewhere/favicon.ico"],
            id="simple_icon",
        ),
        pytest.param(
            """<link rel="icon" href="https://somewhere/favicon.ico">""",
            ["https://somewhere/favicon.ico"],
            id="simple_icon",
        ),
        pytest.param(
            """<link rel="icon">""",
            [],
            id="icon_href_missing",
        ),
        pytest.param(
            """<link rel="shortcut icon" href="https://somewhere/favicon.ico">""",
            ["https://somewhere/favicon.ico"],
            id="simple_shortcut_icon",
        ),
        pytest.param(
            """<link rel="icon" sizes="48x48" href="https://somewhere/favicon.ico">
            <link rel="icon" sizes="96x96" href="https://somewhere/favicon.ico">""",
            ["https://somewhere/favicon.ico"],
            id="no_duplicates",
        ),
        pytest.param(
            """<link rel="icon" sizes="96x96" href="https://somewhere/favicon1.ico">
            <link rel="icon" sizes="48x48" href="https://somewhere/favicon2.ico">""",
            ["https://somewhere/favicon2.ico", "https://somewhere/favicon1.ico"],
            id="sort_by_size",
        ),
        pytest.param(
            Path("tests/data-special/icons.html").read_text(),
            [
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/android-chrome-192x192.png",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon-96x96.png",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon-32x32.png",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon.ico",
                "https://womenshistory.si.edu//sites/default/themes/si_sawhm/favicons/favicon-16x16.png",
            ],
            id="real_life",
        ),
        pytest.param(
            """<link rel="shortcut icon" sizes="aaxbb" href="https://somewhere/favicon.ico">""",
            ["https://somewhere/favicon.ico"],
            id="bad_sizes_1",
        ),
        pytest.param(
            """<link rel="shortcut icon" sizes="12x12x12" href="https://somewhere/favicon.ico">""",
            ["https://somewhere/favicon.ico"],
            id="bad_sizes_2",
        ),
    ],
)
def test_find_and_sort_icons(html, expected):
    assert find_and_sort_icons(html) == expected


@pytest.mark.parametrize(
    "unsorted, expected",
    [
        pytest.param([], [], id="empty"),
        pytest.param(
            [IconUrlAndSize("url1", None, None)],
            [IconUrlAndSize("url1", None, None)],
            id="one_item1",
        ),
        pytest.param(
            [IconUrlAndSize("url1", 12, 12)],
            [IconUrlAndSize("url1", 12, 12)],
            id="one_item2",
        ),
        pytest.param(
            [IconUrlAndSize("url1", None, None), IconUrlAndSize("url2", None, None)],
            [IconUrlAndSize("url1", None, None), IconUrlAndSize("url2", None, None)],
            id="two_items_without_size1",
        ),
        pytest.param(
            [IconUrlAndSize("url3", None, None), IconUrlAndSize("url2", None, None)],
            [IconUrlAndSize("url3", None, None), IconUrlAndSize("url2", None, None)],
            id="two_items_without_size2",
        ),
        pytest.param(
            [IconUrlAndSize("url3", None, None), IconUrlAndSize("url2", 12, 12)],
            [IconUrlAndSize("url3", None, None), IconUrlAndSize("url2", 12, 12)],
            id="two_items_with_size1",  # no change because 12x12 is too small
        ),
        pytest.param(
            [IconUrlAndSize("url3", 12, 12), IconUrlAndSize("url2", None, None)],
            [IconUrlAndSize("url3", 12, 12), IconUrlAndSize("url2", None, None)],
            id="two_items_with_size1",  # no change because 12x12 is too small
        ),
        pytest.param(
            [IconUrlAndSize("url3", None, None), IconUrlAndSize("url2", 48, 48)],
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", None, None)],
            id="two_items_with_size2",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 48, 48), IconUrlAndSize("url2", None, None)],
            [IconUrlAndSize("url3", 48, 48), IconUrlAndSize("url2", None, None)],
            id="two_items_with_size2",
        ),
        pytest.param(
            [IconUrlAndSize("url3", None, None), IconUrlAndSize("url2", 96, 96)],
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", None, None)],
            id="two_items_with_size3",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", None, None)],
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", None, None)],
            id="two_items_with_size3",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 12, 12), IconUrlAndSize("url2", 96, 96)],
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 12, 12)],
            id="two_items_with_size4",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 128, 128), IconUrlAndSize("url2", 96, 96)],
            [IconUrlAndSize("url3", 128, 128), IconUrlAndSize("url2", 96, 96)],
            id="two_items_with_size5",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 128, 128)],
            [IconUrlAndSize("url3", 128, 128), IconUrlAndSize("url2", 96, 96)],
            id="two_items_with_size5",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 12, 12), IconUrlAndSize("url2", 26, 26)],
            [IconUrlAndSize("url2", 26, 26), IconUrlAndSize("url3", 12, 12)],
            id="two_items_with_size6",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 26, 26), IconUrlAndSize("url3", 12, 12)],
            [IconUrlAndSize("url2", 26, 26), IconUrlAndSize("url3", 12, 12)],
            id="two_items_with_size7",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 12, 12)],
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 12, 12)],
            id="two_items_with_size8",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 96, 96)],
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 96, 96)],
            id="two_items_with_size9",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 12, 12), IconUrlAndSize("url2", 48, 48)],
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 12, 12)],
            id="two_items_with_size10",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 96, 96), IconUrlAndSize("url2", 48, 48)],
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 96, 96)],
            id="two_items_with_size11",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 48, 48)],
            [IconUrlAndSize("url2", 48, 48), IconUrlAndSize("url3", 48, 48)],
            id="two_items_with_size12",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 96, 96)],
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 96, 96)],
            id="two_items_with_size12",
        ),
        pytest.param(
            [IconUrlAndSize("url3", 32, 32), IconUrlAndSize("url2", 96, 96)],
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 32, 32)],
            id="two_items_with_size13",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 32, 32)],
            [IconUrlAndSize("url2", 96, 96), IconUrlAndSize("url3", 32, 32)],
            id="two_items_with_size14",
        ),
        pytest.param(
            [IconUrlAndSize("url2", 26, 26), IconUrlAndSize("url3", 26, 26)],
            [IconUrlAndSize("url2", 26, 26), IconUrlAndSize("url3", 26, 26)],
            id="two_items_with_size6",
        ),
    ],
)
def test_sort_icons(unsorted, expected):
    assert sort_icons(unsorted) == expected
    if len(unsorted) == 2:
        if unsorted[0] == expected[1]:
            assert unsorted[0] < unsorted[1]
            assert unsorted[1] > unsorted[0]
