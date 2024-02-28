## This file is almost a plain translation from a JavaScript file.
## https://github.com/webrecorder/wabac.js/blob/219830cea0a732bdd72ce100fcfd2f3a1c9c3607/src/rewrite/dsruleset.js
## Partly translated by a human, partly by ChatGPT.

## The ruleset should be kept in sync with the original ones, but there is no easy
## automatic process for that at the moment.


import json
import re
from collections.abc import Iterable
from dataclasses import dataclass

from warc2zim.content_rewriting.js import (
    TransformationAction,
    TransformationRule,
    add_prefix,
    m2str,
)
from warc2zim.content_rewriting.rx_replacer import add_around, add_suffix, replace_all


@dataclass
class SpecificRules:
    contains: list[str]
    rx_rules: list[TransformationRule]


MAX_BITRATE = 5000000


def set_max_bitrate(_opts: dict) -> int:
    max_bitrate = MAX_BITRATE

    # Extra opts is used in wabac, but we never set it ourself here.
    # Let's comment it until we figure out
    # extra_opts = opts["response"]["extraOpts"] if "response" in opts else None
    # if extra_opts["save"]:
    #    opts["save"]["maxBitrate"] = maxBitrate
    # elif extra_opts and extra_opts["maxBitrate"]:
    #    max_bitrate = extra_opts["maxBitrate"]

    return max_bitrate


def rule_rewrite_twitter_video(prefix: str) -> TransformationAction:
    def rewrite(m_object: re.Match, opts: dict) -> str:
        string = m_object[0]
        if not opts:
            return string

        orig_string = string

        try:
            w_x_h = re.compile(r"([\d]+)x([\d]+)")

            max_bitrate = set_max_bitrate(opts)

            string = string[len(prefix) :]

            data = json.loads(string)

            best_variant = None
            best_bitrate = 0

            for variant in data["variants"]:
                if (
                    variant.get("content_type")
                    and variant["content_type"] != "video/mp4"
                ) or (variant.get("type") and variant["type"] != "video/mp4"):
                    continue

                if (
                    variant.get("bitrate")
                    and variant["bitrate"] > best_bitrate
                    and variant["bitrate"] <= max_bitrate
                ):
                    best_variant = variant
                    best_bitrate = variant["bitrate"]
                elif variant.get("src"):
                    matched = w_x_h.search(variant["src"])
                    if matched:
                        bitrate = int(matched.group(1)) * int(matched.group(2))
                        if bitrate > best_bitrate:
                            best_bitrate = bitrate
                            best_variant = variant

            if best_variant:
                data["variants"] = [best_variant]

            return prefix + json.dumps(data)

        except Exception:
            return orig_string

    return rewrite


@m2str
def rule_rewrite_vimeo_config(string: str) -> str:
    try:
        config = json.loads(string)
    except Exception:
        return string

    if config and config.get("request") and config["request"].get("files"):
        files = config["request"]["files"]
        if isinstance(files.get("progressive"), list) and len(files["progressive"]) > 0:
            if "dash" in files:
                files["__dash"] = files["dash"]
                del files["dash"]
            if "hls" in files:
                files["__hls"] = files["hls"]
                del files["hls"]

            return json.dumps(config)

    return re.sub("query_string_ranges=1", "query_string_ranges=0", string)


def rule_rewrite_vimeo_dash_manifest(m_object: re.Match, opts: dict | None) -> str:
    string = m_object[0]
    if not opts:
        return string

    vimeo_manifest = None

    max_bitrate = set_max_bitrate(opts)

    try:
        vimeo_manifest = json.loads(string)
    except Exception:
        return string

    def filter_by_bitrate(array, max_bitrate, mime):
        if not array:
            return None

        best_variant = 0
        best_bitrate = None

        for variant in array:
            if (
                variant.get("mime_type") == mime
                and variant.get("bitrate") > best_bitrate
                and variant.get("bitrate") <= max_bitrate
            ):
                best_bitrate = variant.get("bitrate")
                best_variant = variant

        return [best_variant] if best_variant else array

    vimeo_manifest["video"] = filter_by_bitrate(
        vimeo_manifest.get("video"), max_bitrate, "video/mp4"
    )
    vimeo_manifest["audio"] = filter_by_bitrate(
        vimeo_manifest.get("audio"), max_bitrate, "audio/mp4"
    )

    return json.dumps(vimeo_manifest)


# This set of rules tell which rules to apply depending on the url of the content
# First rule to match stops the lookup, so rules have to be sorted accordingly.
RULES = [
    SpecificRules(
        ["youtube.com", "youtube-nocookie.com"],
        [
            (
                re.compile(r"ytplayer.load\(\);"),
                add_prefix(
                    'ytplayer.config.args.dash = "0";'
                    ' ytplayer.config.args.dashmpd = ""; '
                ),
            ),
            (
                re.compile(r"yt\.setConfig.*PLAYER_CONFIG.*args\":\s*{"),
                add_suffix(' "dash": "0", dashmpd: "", '),
            ),
            (
                re.compile(r"(?:\"player\":|ytplayer\.config).*\"args\":\s*{"),
                add_suffix('"dash":"0","dashmpd":"",'),
            ),
            (
                re.compile(r"yt\.setConfig.*PLAYER_VARS.*?{"),
                add_suffix('"dash":"0","dashmpd":"",'),
            ),
            (
                re.compile(r"ytplayer.config={args:\s*{"),
                add_suffix('"dash":"0","dashmpd":"",'),
            ),
            (re.compile(r"\"0\"\s*?==\s*?\w+\.dash&&", re.M), replace_all("1&&")),
        ],
    ),
    SpecificRules(
        ["player.vimeo.com/video/"],
        [(re.compile(r"^\{.+\}$"), rule_rewrite_vimeo_config)],
    ),
    SpecificRules(
        ["master.json?query_string_ranges=0", "master.json?base64"],
        [(re.compile(r"r^\{.+\}$"), rule_rewrite_vimeo_dash_manifest)],
    ),
    SpecificRules(
        ["facebook.com/"],
        [
            (re.compile(r"\"dash_"), replace_all('"__nodash__')),
            (re.compile(r"_dash\""), replace_all('__nodash__"')),
            (re.compile(r"_dash_"), replace_all("__nodash__")),
            (
                re.compile(r"\"debugNoBatching\s?\":(?:false|0)"),
                replace_all('"debugNoBatching":true'),
            ),
        ],
    ),
    SpecificRules(
        ["instagram.com/"],
        [
            (
                re.compile(r"\"is_dash_eligible\":(?:true|1)"),
                replace_all('"is_dash_eligible":false'),
            ),
            (
                re.compile(r"\"debugNoBatching\s?\":(?:false|0)"),
                replace_all('"debugNoBatching":true'),
            ),
        ],
    ),
    SpecificRules(
        ["api.twitter.com/2/", "twitter.com/i/api/2/", "twitter.com/i/api/graphql/"],
        [
            (
                re.compile(r"\"video_info\":.*?}]}"),
                rule_rewrite_twitter_video('"video_info":'),
            )
        ],
    ),
    SpecificRules(
        ["cdn.syndication.twimg.com/tweet-result"],
        [
            (
                re.compile(r"\"video\":.*?viewCount\":\d+}"),
                rule_rewrite_twitter_video('"video":'),
            )
        ],
    ),
    SpecificRules(
        ["/vqlweb.js"],
        [
            (
                re.compile(
                    r"b\w+\.updatePortSize\(\);this\.updateApplicationSize\(\)(?![*])",
                    re.I | re.M,
                ),
                add_around("/*", "*/"),
            )
        ],
    ),
]


def get_ds_rules(path: str) -> Iterable[TransformationRule]:
    """
    This build a domain specifc Rewriter (given in rewriter_class), by passing a set of
    extra rules to the rewriter if needed.
    """

    for rule in RULES:
        for pattern in rule.contains:
            if pattern in path:
                return rule.rx_rules

    return []
