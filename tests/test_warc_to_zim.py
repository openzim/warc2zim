#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

import io
import json
import pathlib
import re
import shutil
import time
from urllib.parse import unquote

import pytest
import requests
from warcio.statusandheaders import StatusAndHeaders
from warcio.warcwriter import WARCWriter
from zimscraperlib.image.conversion import convert_image, convert_svg2png
from zimscraperlib.image.optimization import optimize_png
from zimscraperlib.image.probing import format_for
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.rewriting.url_rewriting import REPLAY_MARKER
from zimscraperlib.zim import Archive

from warc2zim.__about__ import __version__
from warc2zim.converter import iter_warc_records
from warc2zim.main import main
from warc2zim.utils import get_record_url

ZIM_ILLUSTRATION_SIZE = 48

TEST_DATA_DIR = pathlib.Path(__file__).parent / "data"
# special data dir for WARC files which are not supposed to be ran in the
# `test_all_warcs_root_dir` test
TEST_DATA_SPECIAL_DIR = pathlib.Path(__file__).parent / "data-special"

SCRAPER_SUFFIX = "zimit x.y.z-devw"

# ============================================================================
CMDLINES = [
    ["example-response.warc"],
    ["example-response.warc", "--progress-file", "progress.json"],
    ["example-revisit.warc.gz"],
    [
        "example-revisit.warc.gz",
        "-u",
        "http://example.iana.org/",
        "--lang",
        "eng",
    ],
    [
        "example-utf8.warc",
        "-u",
        "https://httpbin.org/anything/utf8=%E2%9C%93?query=test&a=b&1=%E2%9C%93",
    ],
    ["single-page-test.warc"],
]


@pytest.fixture(params=CMDLINES, ids=[" ".join(cmds) for cmds in CMDLINES])
def cmdline(request):
    return request.param


# ============================================================================
FUZZYCHECKS = [
    {
        "filename": "video-yt.warc.gz",
        "entries": [
            REPLAY_MARKER
            + "youtube.fuzzy.replayweb.page/get_video_info?video_id=aT-Up5Y4uRI",
            REPLAY_MARKER + "youtube.fuzzy.replayweb.page/videoplayback?id="
            "o-AE3bg3qVNY-gAWwYgL52vgpHKJe9ijdbu2eciNi5Uo_w",
        ],
    },
    {
        "filename": "video-yt-2.warc.gz",
        "entries": [
            REPLAY_MARKER
            + "youtube.fuzzy.replayweb.page/youtubei/v1/player?videoId=aT-Up5Y4uRI",
            REPLAY_MARKER + "youtube.fuzzy.replayweb.page/videoplayback?id="
            "o-AGDtIqpFRmvgVVZk96wgGyFxL_SFSdpBxs0iBHatQpRD",
        ],
    },
    {
        "filename": "video-vimeo.warc.gz",
        "entries": [
            REPLAY_MARKER + "vimeo.fuzzy.replayweb.page/video/347119375",
            REPLAY_MARKER
            + "vimeo-cdn.fuzzy.replayweb.page/01/4423/13/347119375/1398505169.mp4",
        ],
    },
]


@pytest.fixture(params=FUZZYCHECKS, ids=[fuzzy["filename"] for fuzzy in FUZZYCHECKS])
def fuzzycheck(request):
    return request.param


# ============================================================================
class TestWarc2Zim:
    def list_articles(self, zimfile):
        zim_fh = Archive(zimfile)
        for x in range(zim_fh.entry_count):
            yield zim_fh.get_entry_by_id(x)

    def get_main_entry_with_redirect(self, zimfile):
        zim_fh = Archive(zimfile)
        if zim_fh.main_entry.is_redirect:
            return zim_fh.main_entry.get_redirect_entry()
        return zim_fh.main_entry

    def get_metadata(self, zimfile, name):
        zim_fh = Archive(zimfile)
        return zim_fh.get_metadata(name)

    def get_article(self, zimfile, path):
        zim_fh = Archive(zimfile)
        return zim_fh.get_content(path)

    def get_article_raw(self, zimfile, path):
        zim_fh = Archive(zimfile)
        return zim_fh.get_item(path)

    def assert_item_exist(self, zimfile, path):
        zim_fh = Archive(zimfile)
        assert zim_fh.get_item(path)

    def assert_item_does_not_exist(self, zimfile, path):
        zim_fh = Archive(zimfile)
        try:
            payload = zim_fh.get_item(path)
        except KeyError:
            payload = None
        assert payload is None

    def verify_warc_and_zim(self, warcfile, zimfile):
        assert pathlib.Path(warcfile).is_file()
        assert pathlib.Path(zimfile).is_file()

        # [TOFIX]
        head_insert = b""

        # track to avoid checking duplicates, which are not written to ZIM
        warc_urls = set()

        zim_fh = Archive(zimfile)

        assert zim_fh.get_text_metadata("Scraper").startswith(f"warc2zim {__version__}")
        assert zim_fh.get_text_metadata("X-ContentDate")

        for record in iter_warc_records([warcfile]):
            url = get_record_url(record)
            if not url:
                continue

            if url in warc_urls:
                continue

            if record.rec_type not in (("response", "resource", "revisit")):
                continue

            # ignore revisit records that are to the same url
            if (
                record.rec_type == "revisit"
                and record.rec_headers["WARC-Refers-To-Target-URI"] == url
            ):
                continue

            # parse headers as record, ensure headers match
            url_no_scheme = url.split("//", 2)[1]

            if "www.youtube.com/embed" in url_no_scheme:
                # We know that those url are rewritten in zim. Don't check for them.
                break

            url_no_scheme = re.sub(r"\?\d+$", "?", url_no_scheme)

            # remove user/password
            if "@" in url_no_scheme:
                at_index = url_no_scheme.index("@")
                if at_index >= 0:
                    if "/" in url_no_scheme:
                        slash_index = url_no_scheme.index("/")
                        if at_index < slash_index:
                            url_no_scheme = url_no_scheme[at_index + 1 :]
                    else:
                        url_no_scheme = url_no_scheme[at_index + 1 :]

            # remove trailing ?
            if url_no_scheme.endswith("?"):
                url_no_scheme = url_no_scheme[:-1]

            # unquote url since everything is not encoded in ZIM
            url_no_scheme = unquote(url_no_scheme)

            # ensure payloads match
            try:
                payload = zim_fh.get_item(REPLAY_MARKER + url_no_scheme)
            except KeyError:
                payload = None

            if record.http_headers and record.http_headers.get("Content-Length") == "0":
                if record.http_headers.get("Location"):
                    assert payload  # this is a redirect, it must be handled
                else:
                    assert not payload
            elif record.rec_type == "revisit":
                # We must have a payload
                # We should check with the content of the targeted record...
                # But difficult to test as we don't have it
                assert payload
            elif record.rec_type == "response":
                # We must have a payload
                assert payload
                payload_content = (
                    payload.content.tobytes()  # pyright:ignore[reportAttributeAccessIssue]
                )

                # if HTML, still need to account for the head insert, otherwise should
                # have exact match
                if payload.mimetype.startswith(  # pyright:ignore[reportAttributeAccessIssue]
                    "text/html"
                ):
                    assert head_insert in payload_content
            elif record.rec_type == "resource":
                # we do not want to embed resources "as-is"
                assert not payload

            warc_urls.add(url)

    def rebuild_favicon_bytes(self, zim, favicon_path) -> bytes:
        favicon_bytes = self.get_article(
            zim,
            favicon_path,
        )
        assert favicon_bytes
        dst = io.BytesIO()
        if format_for(io.BytesIO(favicon_bytes), from_suffix=False) == "SVG":
            convert_svg2png(
                io.BytesIO(favicon_bytes),
                dst,
                ZIM_ILLUSTRATION_SIZE,
                ZIM_ILLUSTRATION_SIZE,
            )
        else:
            convert_image(io.BytesIO(favicon_bytes), dst, fmt="PNG")
            resize_image(
                dst,
                width=ZIM_ILLUSTRATION_SIZE,
                height=ZIM_ILLUSTRATION_SIZE,
                method="cover",
            )
        dst.seek(0)
        optimized = io.BytesIO()
        optimize_png(dst, optimized)
        return optimized.getvalue()

    def test_warc_to_zim_specify_params_and_metadata(self, tmp_path):
        zim_output = "zim-out-filename.zim"
        main(
            [
                "-v",
                str(TEST_DATA_DIR / "example-response.warc"),
                "--name",
                "example-response",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--tags",
                " foo   ;bar; ; some;_foo:bar;_foo_,_bar_",
                "--desc",
                "test zim",
                "--title",
                "Some Title",
                "--scraper-suffix",
                SCRAPER_SUFFIX,
            ]
        )

        zim_output = tmp_path / zim_output

        assert pathlib.Path(zim_output).is_file()

        all_articles = {
            article.path: article.title for article in self.list_articles(zim_output)
        }

        assert all_articles == {
            # entries from WARC
            REPLAY_MARKER + "example.com/": "Example Domain",
            "_zim_static/__wb_module_decl.js": "_zim_static/__wb_module_decl.js",
            "_zim_static/wombat.js": "_zim_static/wombat.js",
            "_zim_static/wombatSetup.js": "_zim_static/wombatSetup.js",
        }

        zim_fh = Archive(zim_output)

        # ZIM metadata
        assert list(zim_fh.metadata.keys()) == [
            "Counter",
            "Creator",
            "Date",
            "Description",
            "Language",
            "Name",
            "Publisher",
            "Scraper",
            "Tags",
            "Title",
            "X-ContentDate",
        ]

        assert zim_fh.has_fulltext_index
        assert zim_fh.has_title_index

        assert self.get_metadata(zim_output, "Description") == b"test zim"
        # we compare sets of tags since tags ordering has no meaning
        assert set(
            self.get_metadata(zim_output, "Tags").decode("utf-8").split(";")
        ) == {
            "_ftindex:yes",
            "_category:other",
            "some",
            "foo",
            "bar",
            "_foo:bar",
            "_foo_,_bar_",
        }
        assert self.get_metadata(zim_output, "Title") == b"Some Title"

        assert (
            zim_fh.get_text_metadata("Scraper") == f"warc2zim {__version__},"
            "webrecorder.io 2.0 (warcprox 1.4-20151022181819-1a48f12),zimit x.y.z-devw"
        )
        assert zim_fh.get_text_metadata("X-ContentDate") == "2016-02-25"

    def test_warc_to_zim_main(self, cmdline, tmp_path):
        # intput filename
        filename = cmdline[0]

        # set intput filename (first arg) to absolute path from test dir
        warcfile = TEST_DATA_DIR / filename
        cmdline[0] = str(warcfile)

        cmdline.extend(["--output", str(tmp_path), "--name", filename])

        main(cmdline)

        zimfile = filename + "_" + time.strftime("%Y-%m") + ".zim"

        if "--progress-file" in cmdline:
            with open(tmp_path / "progress.json") as fh:
                progress = json.load(fh)
                assert (
                    progress["written"] > 0
                    and progress["total"] > 0
                    and progress["written"] <= progress["total"]
                )

        self.verify_warc_and_zim(warcfile, tmp_path / zimfile)

    def test_same_domain_only(self, tmp_path):
        zim_output = "same-domain.zim"
        main(
            [
                str(TEST_DATA_DIR / "example-revisit.warc.gz"),
                "--favicon",
                "http://example.com/favicon.ico",
                "--include-domains",
                "example.com/",
                "--lang",
                "eng",
                "--zim-file",
                zim_output,
                "--name",
                "same-domain",
                "--output",
                str(tmp_path),
            ]
        )

        zim_output = tmp_path / zim_output

        for article in self.list_articles(zim_output):
            url = article.path
            # ignore the replay files, which have only one path segment
            if not url.startswith("_zim_static/"):
                assert url.startswith(REPLAY_MARKER + "example.com/")

    def test_revisit_with_unresolvable_target_is_skipped(self, tmp_path):
        """A revisit whose referenced response cannot be found anywhere in the
        WARC(s) must be safely skipped, not crash the scraper."""
        warc_path = tmp_path / "revisit-unresolvable.warc.gz"
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)

            home_html = b"<html><body>home</body></html>"
            writer.write_record(
                writer.create_warc_record(
                    "https://example.com/",
                    "response",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [
                            ("Content-Type", "text/html; charset=utf-8"),
                            ("Content-Length", str(len(home_html))),
                        ],
                    ),
                    payload=io.BytesIO(home_html),
                )
            )

            # refers to a URL that was never actually captured as a response
            writer.write_record(
                writer.create_revisit_record(
                    "https://example.com/orphan-revisit",
                    "sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
                    "https://example.com/never-captured",
                    "2026-01-01T00:00:00Z",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [("Content-Type", "text/html; charset=utf-8")],
                    ),
                )
            )

        zim_file = "revisit-unresolvable.zim"
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "revisit-unresolvable",
                "--title",
                "Revisit Unresolvable",
                "--lang",
                "eng",
                "--url",
                "https://example.com/",
            ]
        )

        zim_output = tmp_path / zim_file
        assert b"home" in self.get_article(zim_output, REPLAY_MARKER + "example.com/")
        self.assert_item_does_not_exist(
            zim_output, REPLAY_MARKER + "example.com/orphan-revisit"
        )

    def test_skip_self_redirect(self, tmp_path):
        zim_output = "self-redir.zim"
        main(
            [
                str(TEST_DATA_DIR / "self-redirect.warc"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "self-redir",
            ]
        )

        zim_output = tmp_path / zim_output

    def test_revisit_at_different_path_depth_rewrites_relative_links(self, tmp_path):
        """A revisit record must become an independent ZIM item, not an alias or
        a redirect.

        Neither representation is safe in general: an alias would reuse the
        target's content verbatim, whose relative links were rewritten for the
        target's own path depth and would break under the revisit's (different)
        depth. A redirect would send the reader to the target URL instead,
        breaking any page whose behavior depends on its own URL (e.g. a
        client-side-routed single-page application). Resolving the actual
        payload and rewriting it fresh for the revisit's own path is correct for
        both cases.
        """
        warc_path = tmp_path / "revisit-depth.warc.gz"
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)

            image = b"\x89PNG\r\n\x1a\n fake image bytes"
            writer.write_record(
                writer.create_warc_record(
                    "https://example.com/a/image.png",
                    "response",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [
                            ("Content-Type", "image/png"),
                            ("Content-Length", str(len(image))),
                        ],
                    ),
                    payload=io.BytesIO(image),
                )
            )

            # relative to this record's own path (a/b/page.html), "../image.png"
            # correctly points at a/image.png
            html = b'<html><body><img src="../image.png"></body></html>'
            target_record = writer.create_warc_record(
                "https://example.com/a/b/page.html",
                "response",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 200 OK",
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Content-Length", str(len(html))),
                    ],
                ),
                payload=io.BytesIO(html),
            )
            writer.write_record(target_record)

            # same bytes, but captured one level up ; from here, the very same
            # relative link content ("../image.png") would be WRONG - the right
            # path from here is "a/image.png", with no "../"
            revisit_record = writer.create_revisit_record(
                "https://example.com/page.html",
                "sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
                "https://example.com/a/b/page.html",
                "2026-01-01T00:00:00Z",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 200 OK",
                    [("Content-Type", "text/html; charset=utf-8")],
                ),
            )
            writer.write_record(revisit_record)

        zim_file = "revisit-depth.zim"
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "revisit-depth",
                "--title",
                "Revisit Depth",
                "--lang",
                "eng",
                "--url",
                "https://example.com/a/b/page.html",
            ]
        )

        zim_output = tmp_path / zim_file

        archive = Archive(zim_output)
        revisit_entry = archive.get_entry_by_path(
            REPLAY_MARKER + "example.com/page.html"
        )
        assert not revisit_entry.is_redirect

        target_content = self.get_article(
            zim_output, REPLAY_MARKER + "example.com/a/b/page.html"
        )
        assert b'src="../image.png"' in target_content

        revisit_content = self.get_article(
            zim_output, REPLAY_MARKER + "example.com/page.html"
        )
        assert b'src="a/image.png"' in revisit_content

    def test_revisit_is_served_at_its_own_url_not_redirected(self, tmp_path):
        """A revisit record must be reachable at its own URL, not redirected.

        A single-page application's client-side router decides what to render
        by reading its own URL ; byte-identical static shell markup across two
        different routes (e.g. the same app shell reused as a custom "page not
        found" document) does not mean the two routes are interchangeable for a
        reader. Redirecting one to the other would permanently hide whatever
        that route was meant to render.
        """
        warc_path = tmp_path / "revisit-own-url.warc.gz"
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)

            shell_html = b"<html><body>app shell</body></html>"
            writer.write_record(
                writer.create_warc_record(
                    "https://example.com/",
                    "response",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [
                            ("Content-Type", "text/html; charset=utf-8"),
                            ("Content-Length", str(len(shell_html))),
                        ],
                    ),
                    payload=io.BytesIO(shell_html),
                )
            )

            # same bytes as the homepage, captured as a revisit at a sibling path -
            # exactly the shape of a single-page app reusing its shell as the
            # document for an otherwise-dynamic, client-rendered route
            revisit_record = writer.create_revisit_record(
                "https://example.com/app-route",
                "sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
                "https://example.com/",
                "2026-01-01T00:00:00Z",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 200 OK",
                    [("Content-Type", "text/html; charset=utf-8")],
                ),
            )
            writer.write_record(revisit_record)

        zim_file = "revisit-own-url.zim"
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "revisit-own-url",
                "--title",
                "Revisit Own URL",
                "--lang",
                "eng",
                "--url",
                "https://example.com/",
            ]
        )

        zim_output = tmp_path / zim_file
        archive = Archive(zim_output)
        revisit_entry = archive.get_entry_by_path(
            REPLAY_MARKER + "example.com/app-route"
        )
        assert not revisit_entry.is_redirect

        assert b"app shell" in self.get_article(
            zim_output, REPLAY_MARKER + "example.com/app-route"
        )

    def test_revisit_resolves_payload_across_warc_files(self, tmp_path):
        """A revisit must resolve its payload even when the response it refers to
        was captured in a different WARC file than the revisit itself."""
        warc_dir = tmp_path / "input"
        warc_dir.mkdir()

        html = b"<html><body>shared content</body></html>"
        with open(warc_dir / "0-response.warc.gz", "wb") as output:
            writer = WARCWriter(output, gzip=True)
            writer.write_record(
                writer.create_warc_record(
                    "https://example.com/",
                    "response",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [
                            ("Content-Type", "text/html; charset=utf-8"),
                            ("Content-Length", str(len(html))),
                        ],
                    ),
                    payload=io.BytesIO(html),
                )
            )

        with open(warc_dir / "1-revisit.warc.gz", "wb") as output:
            writer = WARCWriter(output, gzip=True)
            writer.write_record(
                writer.create_revisit_record(
                    "https://example.com/other-page",
                    "sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
                    "https://example.com/",
                    "2026-01-01T00:00:00Z",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [("Content-Type", "text/html; charset=utf-8")],
                    ),
                )
            )

        zim_file = "revisit-cross-file.zim"
        main(
            [
                str(warc_dir),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "revisit-cross-file",
                "--title",
                "Revisit Cross File",
                "--lang",
                "eng",
                "--url",
                "https://example.com/",
            ]
        )

        zim_output = tmp_path / zim_file
        assert b"shared content" in self.get_article(
            zim_output, REPLAY_MARKER + "example.com/other-page"
        )

    def test_revisit_of_a_revisit_resolves_payload(self, tmp_path):
        """A revisit referring to another, earlier revisit (rather than directly
        to a `response` record) must still resolve to the real payload."""
        warc_path = tmp_path / "revisit-chain.warc.gz"
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)

            html = b"<html><body>shared content</body></html>"
            writer.write_record(
                writer.create_warc_record(
                    "https://example.com/",
                    "response",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [
                            ("Content-Type", "text/html; charset=utf-8"),
                            ("Content-Length", str(len(html))),
                        ],
                    ),
                    payload=io.BytesIO(html),
                )
            )

            # revisit of the response above
            writer.write_record(
                writer.create_revisit_record(
                    "https://example.com/first-revisit",
                    "sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
                    "https://example.com/",
                    "2026-01-01T00:00:00Z",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [("Content-Type", "text/html; charset=utf-8")],
                    ),
                )
            )

            # revisit of the revisit above, not of the original response
            writer.write_record(
                writer.create_revisit_record(
                    "https://example.com/second-revisit",
                    "sha1:3I42H3S6NNFQ2MSVX7XZKYAYSCX5QBYJ",
                    "https://example.com/first-revisit",
                    "2026-01-01T00:00:01Z",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [("Content-Type", "text/html; charset=utf-8")],
                    ),
                )
            )

        zim_file = "revisit-chain.zim"
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "revisit-chain",
                "--title",
                "Revisit Chain",
                "--lang",
                "eng",
                "--url",
                "https://example.com/",
            ]
        )

        zim_output = tmp_path / zim_file
        assert b"shared content" in self.get_article(
            zim_output, REPLAY_MARKER + "example.com/first-revisit"
        )
        assert b"shared content" in self.get_article(
            zim_output, REPLAY_MARKER + "example.com/second-revisit"
        )

    def test_error_status_with_content_is_included(self, tmp_path):
        """A response with a 4xx/5xx status but real content must be included.

        Browsers render such a body exactly like a 200 when one is present (no
        special "friendly error page" substitution happens in modern browsers), so
        there is no reason to drop it just because of its status code. This mimics a
        single-page application serving its full, working app shell as its own
        "page not found" document.
        """
        warc_path = tmp_path / "error-with-content.warc.gz"
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)

            home_html = b"<html><body><a href='/deep-link'>deep link</a></body></html>"
            home_record = writer.create_warc_record(
                "https://example.com/",
                "response",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 200 OK",
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Content-Length", str(len(home_html))),
                    ],
                ),
                payload=io.BytesIO(home_html),
            )
            writer.write_record(home_record)

            deep_link_html = (
                b"<html><head><title>App shell</title></head>"
                b"<body>real, renderable content</body></html>"
            )
            deep_link_record = writer.create_warc_record(
                "https://example.com/deep-link",
                "response",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 404 Not Found",
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Content-Length", str(len(deep_link_html))),
                    ],
                ),
                payload=io.BytesIO(deep_link_html),
            )
            writer.write_record(deep_link_record)

        zim_file = "error-with-content.zim"
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "error-with-content",
                "--title",
                "Error With Content",
                "--lang",
                "eng",
                "--url",
                "https://example.com/",
            ]
        )

        res = self.get_article(
            tmp_path / zim_file, REPLAY_MARKER + "example.com/deep-link"
        )
        assert b"real, renderable content" in res

    def test_include_domains_favicon_and_language(self, tmp_path):
        zim_output = "spt.zim"
        main(
            [
                str(TEST_DATA_DIR / "single-page-test.warc"),
                "-i",
                "reseau-canope.fr",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "spt",
            ]
        )

        zim_output = tmp_path / zim_output

        for article in self.list_articles(zim_output):
            url = article.path
            # ignore the replay files, which have only one path segment
            if not url.startswith("_zim_static/"):
                assert "reseau-canope.fr/" in url

        # test detected language
        assert self.get_metadata(zim_output, "Language") == b"fra"

        # test detected favicon
        zim_favicon = self.get_metadata(zim_output, "Illustration_48x48@1")
        assert zim_favicon

        assert (
            self.rebuild_favicon_bytes(
                zim_output,
                REPLAY_MARKER
                + "lesfondamentaux.reseau-canope.fr/fileadmin/template/img/favicon.ico",
            )
            == zim_favicon
        )

        # test default tags added ; we compare sets of tags since tags ordering has no
        # meaning
        assert set(
            self.get_metadata(zim_output, "Tags").decode("utf-8").split(";")
        ) == {
            "_ftindex:yes",
            "_category:other",
        }

    CANOPE = "https://lesfondamentaux.reseau-canope.fr"
    CANOPE_ZIM = (
        REPLAY_MARKER + "lesfondamentaux.reseau-canope.fr/fileadmin/template/img"
    )

    def _write_canope_pages(self, path: pathlib.Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "url": f"{self.CANOPE}/",
                    "seed": True,
                    "favicon": f"{self.CANOPE}/fileadmin/template/img/logo_canope.png",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_crawler_favicon_overrides_size_ranking(self, tmp_path):
        png = f"{self.CANOPE_ZIM}/logo_canope.png"
        ico = f"{self.CANOPE_ZIM}/favicon.ico"
        base_args = [
            str(TEST_DATA_DIR / "single-page-test.warc"),
            "-i",
            "reseau-canope.fr",
            "--output",
            str(tmp_path),
        ]

        main([*base_args, "--zim-file", "default.zim", "--name", "default"])
        default_zim = tmp_path / "default.zim"
        default_icon = self.get_metadata(default_zim, "Illustration_48x48@1")
        png_bytes = self.rebuild_favicon_bytes(default_zim, png)
        ico_bytes = self.rebuild_favicon_bytes(default_zim, ico)
        assert png_bytes != ico_bytes
        default_is_png = default_icon == png_bytes
        assert default_is_png or default_icon == ico_bytes

        loser = "img/favicon.ico" if default_is_png else "img/logo_canope.png"
        pages_file = tmp_path / "pages.jsonl"
        pages_file.write_text(
            json.dumps(
                {
                    "url": f"{self.CANOPE}/",
                    "seed": True,
                    "favicon": f"{self.CANOPE}/fileadmin/template/{loser}",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        main(
            [
                *base_args,
                "--pages-metadata",
                str(pages_file),
                "--zim-file",
                "crawler.zim",
                "--name",
                "crawler",
            ]
        )
        crawler_icon = self.get_metadata(
            tmp_path / "crawler.zim", "Illustration_48x48@1"
        )
        assert crawler_icon == (ico_bytes if default_is_png else png_bytes)

    def test_crawler_favicon_cli_override(self, tmp_path):
        zim_output = "spt_override.zim"
        pages_file = tmp_path / "pages.jsonl"
        self._write_canope_pages(pages_file)
        main(
            [
                str(TEST_DATA_DIR / "single-page-test.warc"),
                "-i",
                "reseau-canope.fr",
                "--pages-metadata",
                str(pages_file),
                "--favicon",
                f"{self.CANOPE}/fileadmin/template/img/favicon.ico",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "spt_override",
            ]
        )

        zim_output_path = tmp_path / zim_output
        zim_favicon = self.get_metadata(zim_output_path, "Illustration_48x48@1")
        assert zim_favicon

        assert zim_favicon == self.rebuild_favicon_bytes(
            zim_output_path, f"{self.CANOPE_ZIM}/favicon.ico"
        )

    def test_crawler_favicon_auto_discovery(self, tmp_path):
        crawl_dir = tmp_path / "crawl"
        archive_dir = crawl_dir / "archive"
        pages_dir = crawl_dir / "pages"
        archive_dir.mkdir(parents=True)
        pages_dir.mkdir(parents=True)

        shutil.copy(
            TEST_DATA_DIR / "single-page-test.warc",
            archive_dir / "single-page-test.warc",
        )
        self._write_canope_pages(pages_dir / "pages.jsonl")

        zim_output = "spt_autodiscover.zim"
        main(
            [
                str(crawl_dir),
                "-i",
                "reseau-canope.fr",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "spt_autodiscover",
            ]
        )

        zim_output_path = tmp_path / zim_output
        # pages.jsonl must not have been processed as a WARC, ZIM must be valid
        actual_icon = self.get_metadata(zim_output_path, "Illustration_48x48@1")
        expected_icon = self.rebuild_favicon_bytes(
            zim_output_path,
            f"{self.CANOPE_ZIM}/logo_canope.png",
        )
        assert actual_icon == expected_icon

    def test_crawler_favicon_absent_from_warc(self, tmp_path):
        """Falls back when the crawler favicon is not captured."""
        pages_file = tmp_path / "pages.jsonl"
        pages_file.write_text(
            json.dumps(
                {
                    "url": f"{self.CANOPE}/",
                    "seed": True,
                    "favicon": f"{self.CANOPE}/absent_favicon.ico",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        zim_output = "spt_absent.zim"
        main(
            [
                str(TEST_DATA_DIR / "single-page-test.warc"),
                "-i",
                "reseau-canope.fr",
                "--pages-metadata",
                str(pages_file),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "spt_absent",
            ]
        )

        zim_output_path = tmp_path / zim_output
        assert zim_output_path.is_file()
        actual_icon = self.get_metadata(zim_output_path, "Illustration_48x48@1")
        assert actual_icon
        expected_fallback = self.rebuild_favicon_bytes(
            zim_output_path,
            f"{self.CANOPE_ZIM}/favicon.ico",
        )
        assert actual_icon == expected_fallback

    def test_crawler_favicon_auto_discovery_from_warc_file(self, tmp_path):
        """Auto-discover pages.jsonl when WARC file in archive/ is given directly."""
        crawl_dir = tmp_path / "crawl"
        archive_dir = crawl_dir / "archive"
        pages_dir = crawl_dir / "pages"
        archive_dir.mkdir(parents=True)
        pages_dir.mkdir(parents=True)

        warc_path = archive_dir / "single-page-test.warc"
        shutil.copy(TEST_DATA_DIR / "single-page-test.warc", warc_path)
        self._write_canope_pages(pages_dir / "pages.jsonl")

        zim_output = "autodiscover_warc.zim"
        main(
            [
                str(warc_path),
                "-i",
                "reseau-canope.fr",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "autodiscover_warc",
            ]
        )
        zim_output_path = tmp_path / zim_output
        assert zim_output_path.is_file()
        actual_icon = self.get_metadata(zim_output_path, "Illustration_48x48@1")
        expected_icon = self.rebuild_favicon_bytes(
            zim_output_path,
            f"{self.CANOPE_ZIM}/logo_canope.png",
        )
        assert actual_icon == expected_icon

    def test_pages_metadata_not_a_file_and_empty_metadata(self, tmp_path):
        """Handle --pages-metadata pointing to a directory and empty pages.jsonl."""
        invalid_meta_dir = tmp_path / "not_a_file"
        invalid_meta_dir.mkdir()
        zim_output = "dir_meta.zim"
        main(
            [
                str(TEST_DATA_DIR / "single-page-test.warc"),
                "-i",
                "reseau-canope.fr",
                "--pages-metadata",
                str(invalid_meta_dir),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "dir_meta",
            ]
        )
        assert (tmp_path / zim_output).is_file()

        empty_pages = tmp_path / "empty_pages.jsonl"
        empty_pages.write_text("", encoding="utf-8")
        zim_output2 = "empty_meta.zim"
        main(
            [
                str(TEST_DATA_DIR / "single-page-test.warc"),
                "-i",
                "reseau-canope.fr",
                "--pages-metadata",
                str(empty_pages),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output2,
                "--name",
                "empty_meta",
            ]
        )
        assert (tmp_path / zim_output2).is_file()

    def test_website_with_redirect(self, tmp_path):
        zim_output = "kiwix.zim"
        main(
            [
                str(TEST_DATA_DIR / "kiwix-with-redirects.warc.gz"),
                "-u",
                "http://www.kiwix.org",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "kiwix",
            ]
        )

        zim_output = tmp_path / zim_output

        # check that redirections have been followed
        assert (
            self.get_main_entry_with_redirect(zim_output).path
            == REPLAY_MARKER + "kiwix.org/en/"
        )

        # test detected language
        assert self.get_metadata(zim_output, "Language") == b"eng"

        # test detected favicon
        zim_favicon = self.get_metadata(zim_output, "Illustration_48x48@1")
        assert zim_favicon

        assert (
            self.rebuild_favicon_bytes(
                zim_output,
                REPLAY_MARKER + "kiwix.org/favicon.ico",
            )
            == zim_favicon
        )

    def test_all_warcs_root_dir(self, tmp_path):
        zim_output = "test-all.zim"
        main(
            [
                str(TEST_DATA_DIR),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-all",
                "--url",
                "http://example.com",
            ]
        )
        zim_output = tmp_path / zim_output

        # check articles from different warc records in tests/data dir

        # from example.warc.gz
        assert self.get_article(zim_output, REPLAY_MARKER + "example.com/") != b""

        # from single-page-test.warc
        assert (
            self.get_article(
                zim_output,
                REPLAY_MARKER + "lesfondamentaux.reseau-canope.fr/accueil.html",
            )
            != b""
        )

        # timestamp fuzzy match from example-with-timestamp.warc
        assert (
            self.get_article(zim_output, REPLAY_MARKER + "example.com/path.txt") != b""
        )

    def test_fuzzy_urls(self, tmp_path, fuzzycheck):
        zim_output = fuzzycheck["filename"] + ".zim"
        main(
            [
                str(TEST_DATA_DIR / fuzzycheck["filename"]),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-fuzzy",
            ]
        )
        zim_output = tmp_path / zim_output

        for entry in fuzzycheck["entries"]:
            # This should be item and get_article_raw is eq to getItem and it will fail
            # if it is not a item
            self.get_article_raw(zim_output, entry)

    def test_error_bad_main_page(self, tmp_path):
        zim_output_not_created = "zim-out-not-created.zim"
        assert (
            main(
                [
                    "-v",
                    str(TEST_DATA_DIR / "example-response.warc"),
                    "-u",
                    "https://no-such-url.example.com",
                    "--output",
                    str(tmp_path),
                    "--name",
                    "bad",
                    "--zim-file",
                    zim_output_not_created,
                ]
            )
            == 4
        )

    def test_main_page_with_error_status_and_content_is_included(self, tmp_path):
        """A main page returning a 4xx/5xx status with real content must still be
        included and used as the ZIM's main page.

        A 4xx/5xx status on a page's own URL is unusual, but it's that page's own
        business - e.g. an anti-bot challenge page, or a single-page application
        serving its full, working app shell as a "page not found" document for a
        direct deep link (see #506). warc2zim doesn't second-guess it, whatever
        role that URL plays in the ZIM.
        """
        zim_file = "main-entry-403.zim"
        main(
            [
                str(TEST_DATA_DIR / "main-entry-403.warc.gz"),
                "-u",
                "https://wikizilla.org/wiki/Doug",
                "--output",
                str(tmp_path),
                "--name",
                "main-entry-403",
                "--zim-file",
                zim_file,
            ]
        )

        zim_output = tmp_path / zim_file
        assert zim_output.exists()

        main_entry = self.get_main_entry_with_redirect(zim_output)
        assert main_entry.path == REPLAY_MARKER + "wikizilla.org/wiki/Doug"
        assert b"Just a moment" in bytes(main_entry.get_item().content)

    def test_args_only(self):
        # error, name required
        with pytest.raises(SystemExit) as e:
            main([])
        assert e.value.code == 2

        # error, no such output directory
        with pytest.raises(SystemExit) as e:
            main(["--name", "test", "--output", "/no-such-dir"])
            assert e.value.code == 1

        # error, name has invalid characters for Linux filesystem
        with pytest.raises(SystemExit) as e:
            main(["--name", "te/st", "--output", "./"])
            assert e.value.code == 3

        # success, special return code for no output files
        assert main(["--name", "test", "--output", "./"]) == 100

    def test_custom_css(self, tmp_path):
        custom_css = b"* { background-color: red; }"
        custom_css_path = tmp_path / "custom.css"
        with open(custom_css_path, "wb") as fh:
            fh.write(custom_css)

        zim_output = "test-css.zim"

        main(
            [
                str(TEST_DATA_DIR / "example-response.warc"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-css",
                "--custom-css",
                str(custom_css_path),
            ]
        )
        zim_output = tmp_path / zim_output

        res = self.get_article(zim_output, REPLAY_MARKER + "example.com/")
        assert b"static_prefix" not in res
        assert b"../_zim_static/custom.css" in res

        res = self.get_article(zim_output, "_zim_static/custom.css")
        assert custom_css == res

    def test_custom_css_remote(self, tmp_path):
        zim_output = "test-css.zim"
        url = (
            "https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap-reboot.css"
        )

        main(
            [
                str(TEST_DATA_DIR / "example-response.warc"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-css",
                "--custom-css",
                url,
            ]
        )
        zim_output = tmp_path / zim_output

        res = self.get_article(zim_output, REPLAY_MARKER + "example.com/")
        assert b"static_prefix" not in res
        assert b"../_zim_static/custom.css" in res

        res = self.get_article(zim_output, "_zim_static/custom.css")
        assert res == requests.get(url, timeout=10).content

    def test_http_return_codes(self, tmp_path):
        zim_output = "test-http-return-codes.zim"

        main(
            [
                str(TEST_DATA_DIR / "http-return-codes.warc.gz"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-http-return-codes",
            ]
        )
        zim_output = tmp_path / zim_output

        for exising_website_items in [
            "200-response",
            "201-response",
            "202-response",
            "301-internal-redirect-ok",
            "301-external-redirect-ok",
            "302-internal-redirect-ok",
            "302-external-redirect-ok",
            "307-internal-redirect-ok",
            "307-external-redirect-ok",
            "308-internal-redirect-ok",
            "308-external-redirect-ok",
        ]:
            self.assert_item_exist(
                zim_output,
                REPLAY_MARKER + f"website.test.openzim.org/{exising_website_items}",
            )

        self.assert_item_exist(zim_output, REPLAY_MARKER + "www.example.com/")

        for ignored_website_items in [
            "204-response",
            "206-response",
            "300-response",
            "303-response",
            "304-response",
            "305-response",
            "306-response",
            "400-response",
            "401-response",
            "402-response",
            "403-response",
            "404-response",
            "500-response",
            "501-response",
            "502-response",
            "301-internal-redirect-ko",
            "301-external-redirect-ko",
            "302-internal-redirect-ko",
            "302-external-redirect-ko",
            "307-internal-redirect-ko",
            "307-external-redirect-ko",
            "308-internal-redirect-ko",
            "308-external-redirect-ko",
        ]:
            self.assert_item_does_not_exist(
                zim_output,
                REPLAY_MARKER + f"website.test.openzim.org/{ignored_website_items}",
            )

    def test_bad_redirections(self, tmp_path):
        zim_output = "test-bad-redirections.zim"

        main(
            [
                str(TEST_DATA_DIR / "bad-redirections.warc.gz"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-bad-redirections",
            ]
        )
        zim_output = tmp_path / zim_output

        for exising_website_items in [
            "bad-redirections.html",
        ]:
            self.assert_item_exist(
                zim_output,
                REPLAY_MARKER + f"website.test.openzim.org/{exising_website_items}",
            )

        for ignored_website_items in [
            "/bad-redir-loop-A",
            "/bad-redir-loop-B",
            "/bad-redir-loop-C",
            "/bad-redir-loop-D",
            "/bad-redir-target-A",
            "/bad-redir-target-B",
        ]:
            self.assert_item_does_not_exist(
                zim_output,
                REPLAY_MARKER + f"website.test.openzim.org/{ignored_website_items}",
            )

    def test_content_resource_types(self, tmp_path):
        zim_output = "tests_en_content-resource-types.zim"

        main(
            [
                str(TEST_DATA_DIR / "content-resource-types.warc.gz"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "tests_en_content-resource-types",
            ]
        )
        zim_output = tmp_path / zim_output

        res = self.get_article(
            zim_output,
            REPLAY_MARKER + "website.test.openzim.org/content-types/index.html",
        )
        assert b"<!-- WB Insert -->" in res  # simple check that rewriting has been done

        for js_file in [
            "website.test.openzim.org/content-types/script1.js",
            "website.test.openzim.org/content-types/script2.js",
        ]:
            res = self.get_article(zim_output, REPLAY_MARKER + js_file)
            assert b"wombat" in res  # simple check that rewriting has been done

    def test_content_encoding_aliases(self, tmp_path):
        zim_output = "tests_en_qsl.net-encoding-alias.zim"

        main(
            [
                # cannot be processed like other TEST_DATA_DIR warcs since it needs
                # special encoding aliases to be used in --encoding-aliases
                str(TEST_DATA_SPECIAL_DIR / "qsl.net-encoding-alias.warc.gz"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--encoding-aliases",
                "foo=bar,iso-8559-1=iso-8859-1,fii=bor",
                "--name",
                "tests_en_qsl.net-encoding-alias",
            ]
        )
        zim_output = tmp_path / zim_output

        res = self.get_article(
            zim_output, REPLAY_MARKER + "www.qsl.net/vk2jem/swlogs.htm"
        )
        assert b"<!-- WB Insert -->" in res  # simple check that rewriting has been done

    def test_solidaritenum(self, tmp_path):
        zim_output = "solidaritenum.zim"
        main(
            [
                str(TEST_DATA_DIR / "solidaritenum.warc.gz"),
                "--url",
                (
                    "https://www.solidarite-numerique.fr/tutoriels/comprendre-les-cookies/"
                    "?thematique=internet"
                ),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "spt",
            ]
        )

        zim_output = tmp_path / zim_output

        # test detected language
        assert self.get_metadata(zim_output, "Language") == b"fra"

        # test detected favicon
        zim_favicon = self.get_metadata(zim_output, "Illustration_48x48@1")
        assert zim_favicon

        # test favicon is the correct one
        assert (
            self.rebuild_favicon_bytes(
                zim_output,
                REPLAY_MARKER
                + "www.solidarite-numerique.fr/wp-content/themes/snum-v2/images//ico/"
                "favicon.svg",
            )
            == zim_favicon
        )

    def test_overwrite_existing_zim_and_zimit_fail_early(self, tmp_path):
        zim_output = "fail-early-test.zim"
        output_path = tmp_path / zim_output
        test_name = "fail-early-test"
        test_url = "https://example.com/"

        # --- SETUP: Create the target ZIM file first ---

        setup_args = [
            str(TEST_DATA_DIR / "example-response.warc"),
            "--output",
            str(tmp_path),
            "--zim-file",
            zim_output,
            "--name",
            test_name,
            "--url",
            test_url,
        ]
        main(setup_args)
        assert output_path.exists()

        # --- TEST 1: Simulate zimit's 'fail-early' argument check (NO WARC INPUT) ---

        fail_early_args = [
            "--output",
            str(tmp_path),
            "--zim-file",
            zim_output,
            "--name",
            test_name,
            "--url",
            test_url,
        ]

        with pytest.raises(SystemExit) as e:
            main(fail_early_args)

        assert e.value.code == 2

        # --- TEST 2: Validate the successful path (NO WARC INPUT, WITH OVERWRITE) ---
        overwrite_no_input_args = [
            "--output",
            str(tmp_path),
            "--zim-file",
            zim_output,
            "--name",
            test_name,
            "--url",
            test_url,
            "--overwrite",
        ]

        ret_no_input = main(overwrite_no_input_args)
        assert ret_no_input == 100

        # --- TEST 3: Test for successful overwrite (WITH WARC INPUT) ---
        overwrite_full_run_args = [
            str(TEST_DATA_DIR / "example-response.warc"),
            "--output",
            str(tmp_path),
            "--zim-file",
            zim_output,
            "--name",
            test_name,
            "--url",
            test_url,
            "--overwrite",
        ]

        ret_full_run = main(overwrite_full_run_args)
        assert ret_full_run in (None, 0)
        assert output_path.exists()

        # --- TEST 4: Validate that overwrite without --overwrite fails ---
        no_overwrite_full_run_args = [
            str(TEST_DATA_DIR / "example-response.warc"),
            "--output",
            str(tmp_path),
            "--zim-file",
            zim_output,
            "--name",
            test_name,
            "--url",
            test_url,
        ]

        with pytest.raises(SystemExit) as e:
            main(no_overwrite_full_run_args)
        assert e.value.code == 2

    def test_download_filename_content_disposition(self, tmp_path):

        warc_path = tmp_path / "test.warc.gz"
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)
            html = b'<html><body><a href="https://example.com/download?id=1">Download</a></body></html>'
            rec1 = writer.create_warc_record(
                "https://example.com/index.html",
                "response",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 200 OK",
                    [
                        ("Content-Type", "text/html; charset=utf-8"),
                        ("Content-Length", str(len(html))),
                    ],
                ),
                payload=io.BytesIO(html),
            )
            writer.write_record(rec1)

            pdf = b"%PDF-1.4 test pdf content %%EOF"
            rec2 = writer.create_warc_record(
                "https://example.com/download?id=1",
                "response",
                http_headers=StatusAndHeaders(
                    "HTTP/1.1 200 OK",
                    [
                        ("Content-Type", "application/pdf"),
                        ("Content-Disposition", 'attachment; filename="book.pdf"'),
                        ("Content-Length", str(len(pdf))),
                    ],
                ),
                payload=io.BytesIO(pdf),
            )
            writer.write_record(rec2)

        zim_file = "test_disposition.zim"
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "test-disposition",
                "--title",
                "Test Disposition",
                "--lang",
                "eng",
            ]
        )

        zim_path = tmp_path / zim_file
        archive = Archive(zim_path)
        redirect_entry = archive.get_entry_by_path(
            REPLAY_MARKER + "example.com/download?id=1"
        )
        assert redirect_entry.is_redirect
        target = redirect_entry.get_redirect_entry()
        assert target.path == REPLAY_MARKER + "example.com/download?id=1/book.pdf"
        assert not target.is_redirect

    def test_xhtml_end_to_end(self, tmp_path):
        warc_path = tmp_path / "xhtml.warc.gz"
        xhtml = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>XHTML page'
            b"</title></head><body>"
            b'<img src="https://example.com/images/image1.jpg" />'
            b"</body></html>"
        )
        with open(warc_path, "wb") as output:
            writer = WARCWriter(output, gzip=True)
            writer.write_record(
                writer.create_warc_record(
                    "https://example.com/index.xhtml",
                    "response",
                    http_headers=StatusAndHeaders(
                        "HTTP/1.1 200 OK",
                        [
                            ("Content-Type", "application/xhtml+xml; charset=utf-8"),
                            ("Content-Length", str(len(xhtml))),
                        ],
                    ),
                    payload=io.BytesIO(xhtml),
                )
            )

        zim_file = "xhtml.zim"
        # no --url: main page must be guessed from the first HTML-like record
        main(
            [
                str(warc_path),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_file,
                "--name",
                "xhtml-test",
                "--title",
                "XHTML test",
                "--lang",
                "eng",
            ]
        )

        archive = Archive(tmp_path / zim_file)
        main_entry = self.get_main_entry_with_redirect(tmp_path / zim_file)
        assert main_entry.path == REPLAY_MARKER + "example.com/index.xhtml"
        item = main_entry.get_item()
        assert item.mimetype == "text/html"
        content = bytes(item.content).decode()
        assert ' src="images/image1.jpg"' in content
        assert ' src="https://example.com/images/image1.jpg"' not in content
        assert archive.get_entry_by_path(
            REPLAY_MARKER + "example.com/index.xhtml"
        ).title == ("XHTML page")

    def test_jsonp_rewriting_end_to_end(self, tmp_path):
        zim_output = "jsonp-test.zim"

        ret = main(
            [
                str(TEST_DATA_SPECIAL_DIR / "jsonp.warc.gz"),
                "--url",
                "https://website.test.openzim.org/jsonp.html",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "jsonp-test",
            ]
        )
        assert ret in (None, 0)

        zim_path = tmp_path / zim_output
        zim = Archive(zim_path)
        article_paths = {zim.get_entry_by_id(i).path for i in range(zim.entry_count)}

        jsonp_path = next(
            path
            for path in article_paths
            if path.startswith(
                REPLAY_MARKER + "website.test.openzim.org/jsonp/object.js"
            )
        )
        jsonp_content = self.get_article(zim_path, jsonp_path)
        assert b'handleObject({"message":"hello","count":3});' in jsonp_content
        assert b"recordedCallback" not in jsonp_content

        regular_js_path = next(
            path
            for path in article_paths
            if path.startswith(
                REPLAY_MARKER + "website.test.openzim.org/jsonp/not-jsonp.js"
            )
        )
        regular_js_content = self.get_article(zim_path, regular_js_path)
        assert b"function initLoader()" in regular_js_content
        assert b"loaderReady" in regular_js_content
        assert b"wombat" in regular_js_content.lower()
