import re

import pytest

from warc2zim.url_rewriting import FUZZY_RULES

from .utils import ContentForTests


@pytest.fixture(
    params=[
        ContentForTests(
            "foobargooglevideo.com/videoplayback?id=1576&key=value",
            "youtube.fuzzy.replayweb.page/videoplayback?id=1576",
        ),
        ContentForTests(
            "foobargooglevideo.com/videoplayback?some=thing&id=1576",
            "youtube.fuzzy.replayweb.page/videoplayback?id=1576",
        ),
        ContentForTests(
            "foobargooglevideo.com/videoplayback?some=thing&id=1576&key=value",
            "youtube.fuzzy.replayweb.page/videoplayback?id=1576",
        ),
        # videoplayback is not followed by `?`
        ContentForTests(
            "foobargooglevideo.com/videoplaybackandfoo?some=thing&id=1576&key=value"
        ),
        # No googlevideo.com in url
        ContentForTests(
            "foobargoogle_video.com/videoplaybackandfoo?some=thing&id=1576&key=value"
        ),
    ]
)
def google_video_url(request):
    yield request.param


def test_googlevideo(google_video_url):
    rule = FUZZY_RULES[0]
    rewritten = re.sub(rule["pattern"], rule["replace"], google_video_url.input_str)
    assert rewritten == google_video_url.expected_str
