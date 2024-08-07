#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 nu

import io
import json
import pathlib
import re
import time
from urllib.parse import unquote

import pytest
import requests
from zimscraperlib.image.conversion import convert_image, convert_svg2png, resize_image
from zimscraperlib.image.probing import format_for
from zimscraperlib.zim import Archive

from warc2zim.__about__ import __version__
from warc2zim.converter import iter_warc_records
from warc2zim.main import main
from warc2zim.url_rewriting import HttpUrl, ZimPath, normalize
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
            "youtube.fuzzy.replayweb.page/get_video_info?video_id=aT-Up5Y4uRI",
            "youtube.fuzzy.replayweb.page/videoplayback?id=o-AE3bg3qVNY-gAWwYgL52vgpHKJe9ijdbu2eciNi5Uo_w",
        ],
    },
    {
        "filename": "video-yt-2.warc.gz",
        "entries": [
            "youtube.fuzzy.replayweb.page/youtubei/v1/player?videoId=aT-Up5Y4uRI",
            "youtube.fuzzy.replayweb.page/videoplayback?id=o-AGDtIqpFRmvgVVZk96wgGyFxL_SFSdpBxs0iBHatQpRD",
        ],
    },
    {
        "filename": "video-vimeo.warc.gz",
        "entries": [
            "vimeo.fuzzy.replayweb.page/video/347119375",
            "vimeo-cdn.fuzzy.replayweb.page/01/4423/13/347119375/1398505169.mp4",
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
                payload = zim_fh.get_item(url_no_scheme)
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
                payload_content = payload.content.tobytes()

                # if HTML, still need to account for the head insert, otherwise should
                # have exact match
                if payload.mimetype.startswith("text/html"):
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
        return dst.getvalue()

    @pytest.mark.parametrize(
        "url,zim_path",
        [
            ("https://exemple.com", "exemple.com/"),
            ("https://exemple.com/", "exemple.com/"),
            ("http://example.com/resource", "example.com/resource"),
            ("http://example.com/resource/", "example.com/resource/"),
            (
                "http://example.com/resource/folder/sub.txt",
                "example.com/resource/folder/sub.txt",
            ),
            (
                "http://example.com/resource/folder/sub",
                "example.com/resource/folder/sub",
            ),
            (
                "http://example.com/resource/folder/sub?foo=bar",
                "example.com/resource/folder/sub?foo=bar",
            ),
            (
                "http://example.com/resource/folder/sub?foo=bar#anchor1",
                "example.com/resource/folder/sub?foo=bar",
            ),
            ("http://example.com/resource/#anchor1", "example.com/resource/"),
            ("http://example.com/resource/?foo=bar", "example.com/resource/?foo=bar"),
            ("http://example.com#anchor1", "example.com/"),
            ("http://example.com?foo=bar#anchor1", "example.com/?foo=bar"),
            ("http://example.com/?foo=bar", "example.com/?foo=bar"),
            ("http://example.com/?foo=ba+r", "example.com/?foo=ba r"),
            (
                "http://example.com/?foo=ba r",
                "example.com/?foo=ba r",
            ),  # situation where the ` ` has not been properly escaped in document
            ("http://example.com/?foo=ba%2Br", "example.com/?foo=ba+r"),
            ("http://example.com/?foo=ba+%2B+r", "example.com/?foo=ba + r"),
            ("http://example.com/#anchor1", "example.com/"),
            (
                "http://example.com/some/path/http://example.com//some/path",
                "example.com/some/path/http:/example.com/some/path",
            ),
            (
                "http://example.com/some/pa?th/http://example.com//some/path",
                "example.com/some/pa?th/http:/example.com/some/path",
            ),
            (
                "http://example.com/so?me/pa?th/http://example.com//some/path",
                "example.com/so?me/pa?th/http:/example.com/some/path",
            ),
            ("http://example.com/resource?", "example.com/resource"),
            ("http://example.com/resource#", "example.com/resource"),
            ("http://user@example.com/resource", "example.com/resource"),
            ("http://user:password@example.com/resource", "example.com/resource"),
            ("http://example.com:8080/resource", "example.com/resource"),
            (
                "http://foobargooglevideo.com/videoplayback?id=1576&key=value",
                "youtube.fuzzy.replayweb.page/videoplayback?id=1576",
            ),  # Fuzzy rule is applied in addition to path transformations
            ("https://xn--exmple-cva.com", "exémple.com/"),
            ("https://xn--exmple-cva.com/", "exémple.com/"),
            ("https://xn--exmple-cva.com/resource", "exémple.com/resource"),
            ("https://exémple.com/", "exémple.com/"),
            ("https://exémple.com/resource", "exémple.com/resource"),
            # host_ip is an invalid hostname according to spec
            ("https://host_ip/", "host_ip/"),
            ("https://host_ip/resource", "host_ip/resource"),
            ("https://192.168.1.1/", "192.168.1.1/"),
            ("https://192.168.1.1/resource", "192.168.1.1/resource"),
            ("http://example.com/res%24urce", "example.com/res$urce"),
            (
                "http://example.com/resource?foo=b%24r",
                "example.com/resource?foo=b$r",
            ),
            ("http://example.com/resource@300x", "example.com/resource@300x"),
            ("http://example.com:8080/resource", "example.com/resource"),
            ("http://user@example.com:8080/resource", "example.com/resource"),
            ("http://user:password@example.com:8080/resource", "example.com/resource"),
            # the two URI below are an illustration of a potential collision (two
            # differents URI leading to the same ZIM path)
            (
                "http://tmp.kiwix.org/ci/test-website/images/urlencoding1_ico%CC%82ne-"
                "de%CC%81buter-Solidarite%CC%81-Nume%CC%81rique_1%40300x.png",
                "tmp.kiwix.org/ci/test-website/images/urlencoding1_icône-débuter-"
                "Solidarité-Numérique_1@300x.png",
            ),
            (
                "https://tmp.kiwix.org/ci/test-website/images/urlencoding1_ico%CC%82ne-"
                "de%CC%81buter-Solidarite%CC%81-Nume%CC%81rique_1@300x.png",
                "tmp.kiwix.org/ci/test-website/images/urlencoding1_icône-débuter-"
                "Solidarité-Numérique_1@300x.png",
            ),
        ],
    )
    def test_normalize(self, url, zim_path):
        assert normalize(HttpUrl(url)).value == ZimPath(zim_path).value

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
            "example.com/": "Example Domain",
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
                assert url.startswith("example.com/")

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
                "lesfondamentaux.reseau-canope.fr/fileadmin/template/img/favicon.ico",
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
        assert self.get_main_entry_with_redirect(zim_output).path == "kiwix.org/en/"

        # test detected language
        assert self.get_metadata(zim_output, "Language") == b"eng"

        # test detected favicon
        zim_favicon = self.get_metadata(zim_output, "Illustration_48x48@1")
        assert zim_favicon

        assert (
            self.rebuild_favicon_bytes(
                zim_output,
                "kiwix.org/favicon.ico",
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
        assert self.get_article(zim_output, "example.com/") != b""

        # from single-page-test.warc
        assert (
            self.get_article(
                zim_output, "lesfondamentaux.reseau-canope.fr/accueil.html"
            )
            != b""
        )

        # timestamp fuzzy match from example-with-timestamp.warc
        assert self.get_article(zim_output, "example.com/path.txt") != b""

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

    def test_error_main_page_unprocessable(self, tmp_path):
        zim_output_not_created = "zim-out-not-created.zim"
        assert (
            main(
                [
                    "-v",
                    str(TEST_DATA_DIR / "main-entry-403.warc.gz"),
                    "-u",
                    "https://wikizilla.org/wiki/Doug",
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
        assert not (pathlib.Path(tmp_path) / zim_output_not_created).exists()

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

        res = self.get_article(zim_output, "example.com/")
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

        res = self.get_article(zim_output, "example.com/")
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
                zim_output, f"website.test.openzim.org/{exising_website_items}"
            )

        self.assert_item_exist(zim_output, "www.example.com/")

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
                zim_output, f"website.test.openzim.org/{ignored_website_items}"
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
                zim_output, f"website.test.openzim.org/{exising_website_items}"
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
                zim_output, f"website.test.openzim.org/{ignored_website_items}"
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
            zim_output, "website.test.openzim.org/content-types/index.html"
        )
        assert b"<!-- WB Insert -->" in res  # simple check that rewriting has been done

        for js_file in [
            "website.test.openzim.org/content-types/script1.js",
            "website.test.openzim.org/content-types/script2.js",
        ]:
            res = self.get_article(zim_output, js_file)
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

        res = self.get_article(zim_output, "www.qsl.net/vk2jem/swlogs.htm")
        assert b"<!-- WB Insert -->" in res  # simple check that rewriting has been done

    def test_solidaritenum(self, tmp_path):
        zim_output = "solidaritenum.zim"
        main(
            [
                str(TEST_DATA_DIR / "solidaritenum.warc.gz"),
                "--url",
                "https://www.solidarite-numerique.fr/tutoriels/comprendre-les-cookies/"
                "?thematique=internet",
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
                "www.solidarite-numerique.fr/wp-content/themes/snum-v2/images/ico/"
                "favicon.svg",
            )
            == zim_favicon
        )
