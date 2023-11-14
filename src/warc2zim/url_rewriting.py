#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim's url rewriting tools

This module is about url and entry path rewriting.
"""

import logging
import re

# Shared logger
logger = logging.getLogger("warc2zim.url_rewriting")


FUZZY_RULES = [
    {
        "match": re.compile(
            # r"//.*googlevideo.com/(videoplayback\?).*(id=[^&]+).*([&]itag=[^&]+).*"
            r"//.*googlevideo.com/(videoplayback\?).*((?<=[?&])id=[^&]+).*"
        ),
        "replace": r"//youtube.fuzzy.replayweb.page/\1\2",
    },
    {
        "match": re.compile(
            r"//(?:www\.)?youtube(?:-nocookie)?\.com/(get_video_info\?)"
            r".*(video_id=[^&]+).*"
        ),
        "replace": r"//youtube.fuzzy.replayweb.page/\1\2",
    },
    {"match": re.compile(r"(\.[^?]+\?)[\d]+$"), "replace": r"\1"},
    {
        "match": re.compile(
            r"//(?:www\.)?youtube(?:-nocookie)?\.com\/(youtubei\/[^?]+).*(videoId[^&]+).*"
        ),
        "replace": r"//youtube.fuzzy.replayweb.page/\1?\2",
    },
    {
        "match": re.compile(r"//(?:www\.)?youtube(?:-nocookie)?\.com/embed/([^?]+).*"),
        "replace": r"//youtube.fuzzy.replayweb.page/embed/\1",
    },
    {
        "match": re.compile(
            r".*(?:gcs-vimeo|vod|vod-progressive)\.akamaized\.net.*?/([\d/]+.mp4)$"
        ),
        "replace": r"vimeo-cdn.fuzzy.replayweb.page/\1",
    },
    {
        "match": re.compile(r".*player.vimeo.com/(video/[\d]+)\?.*"),
        "replace": r"vimeo.fuzzy.replayweb.page/\1",
    },
]


def canonicalize(url):
    """Return a 'canonical' version of the url under which it is stored in the ZIM
    For now, just removing the scheme http:// or https:// scheme
    """
    if url.startswith("https://"):
        return url[8:]

    if url.startswith("http://"):
        return url[7:]

    return url
