#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import os
import time
import json
from io import BytesIO

import pytest
import requests

import libzim.reader
from warcio import ArchiveIterator
from jinja2 import Environment, PackageLoader

from warc2zim.main import warc2zim, HTML_RAW, canonicalize


CMDLINES = [
    ["example-response.warc"],
    ["example-response.warc", "--progress-file", "progress.json"],
    ["example-resource.warc.gz", "--favicon", "https://example.com/some/favicon.ico"],
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


TEST_DATA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")


@pytest.fixture(params=CMDLINES, ids=[" ".join(cmds) for cmds in CMDLINES])
def cmdline(request):
    return request.param


# ============================================================================
class TestWarc2Zim(object):
    def list_articles(self, zimfile):
        zim_fh = libzim.reader.File(zimfile)
        for x in range(zim_fh.article_count):
            yield zim_fh.get_article_by_id(x)

    def get_article(self, zimfile, path):
        zim_fh = libzim.reader.File(zimfile)
        return zim_fh.get_article(path).content.tobytes()

    def get_article_raw(self, zimfile, path):
        zim_fh = libzim.reader.File(zimfile)
        return zim_fh.get_article(path)

    def verify_warc_and_zim(self, warcfile, zimfile):
        assert os.path.isfile(warcfile)
        assert os.path.isfile(zimfile)

        # autoescape=False to allow injecting html entities from translated text
        env = Environment(
            loader=PackageLoader("warc2zim", "templates"),
            extensions=["jinja2.ext.i18n"],
            autoescape=False,
        )

        head_insert = env.get_template("sw_check.html").render().encode("utf-8")

        # track to avoid checking duplicates, which are not written to ZIM
        warc_urls = set()

        zim_fh = libzim.reader.File(zimfile)
        with open(warcfile, "rb") as warc_fh:
            for record in ArchiveIterator(warc_fh):
                url = record.rec_headers["WARC-Target-URI"]
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
                headers = zim_fh.get_article("H/" + url_no_scheme)
                parsed_record = next(
                    ArchiveIterator(BytesIO(headers.content.tobytes()))
                )

                assert record.rec_headers == parsed_record.rec_headers
                assert record.http_headers == parsed_record.http_headers

                # ensure payloads match
                try:
                    payload = zim_fh.get_article("A/" + url_no_scheme)
                except KeyError:
                    payload = None

                if record.rec_type == "revisit" or (
                    record.http_headers
                    and record.http_headers.get("Content-Length") == "0"
                ):
                    assert not payload
                else:
                    payload_content = payload.content.tobytes()

                    # if HTML_RAW, still need to account for the head insert, otherwise should have exact match
                    if payload.mimetype == HTML_RAW:
                        assert head_insert in payload_content
                        assert (
                            payload_content.replace(head_insert, b"")
                            == record.content_stream().read()
                        )
                    else:
                        assert payload_content == record.content_stream().read()

                warc_urls.add(url)

    def test_canonicalize(self):
        assert canonicalize("http://example.com/?foo=bar") == "example.com/?foo=bar"

        assert canonicalize("https://example.com/?foo=bar") == "example.com/?foo=bar"

        assert (
            canonicalize("https://example.com/some/path/http://example.com/?foo=bar")
            == "example.com/some/path/http://example.com/?foo=bar"
        )

        assert (
            canonicalize("example.com/some/path/http://example.com/?foo=bar")
            == "example.com/some/path/http://example.com/?foo=bar"
        )

    def test_warc_to_zim_specify_params_and_metadata(self, tmp_path):
        zim_output = "zim-out-filename.zim"
        warc2zim(
            [
                "-v",
                os.path.join(TEST_DATA_DIR, "example-response.warc"),
                "--name",
                "example-response",
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "-r",
                "https://cdn.jsdelivr.net/npm/@webrecorder/wabac@2.1.0-dev.3/dist/",
                "--tags",
                "some",
                "--tags",
                "foo",
                "--desc",
                "test zim",
                "--tags",
                "bar",
                "--title",
                "Some Title",
            ]
        )

        zim_output = tmp_path / zim_output

        assert os.path.isfile(zim_output)

        all_articles = {
            article.longurl: article.title for article in self.list_articles(zim_output)
        }

        assert all_articles == {
            # entries from WARC
            "A/example.com/": "Example Domain",
            "H/example.com/": "example.com/",
            # replay system files
            "A/index.html": "index.html",
            "A/load.js": "load.js",
            "A/404.html": "404.html",
            "A/sw.js": "sw.js",
            "A/topFrame.html": "topFrame.html",
            # ZIM metadata
            "M/Compression": "Compression",
            "M/Counter": "Counter",
            "M/Creator": "Creator",
            "M/Date": "Date",
            "M/Description": "Description",
            "M/Language": "Language",
            "M/Name": "Name",
            "M/Publisher": "Publisher",
            "M/Scraper": "Scraper",
            "M/Source": "Source",
            "M/Tags": "Tags",
            "M/Title": "Title",
            # Xapian
            "X/fulltext/xapian": "Xapian Fulltext Index",
            "X/title/xapian": "Xapian Title Index",
        }

        assert self.get_article(zim_output, "M/Description") == b"test zim"
        assert (
            self.get_article(zim_output, "M/Tags")
            == b"_ftindex:yes;_category:other;_sw:yes;some;foo;bar"
        )
        assert self.get_article(zim_output, "M/Title") == b"Some Title"

    def test_warc_to_zim(self, cmdline, tmp_path):
        # intput filename
        filename = cmdline[0]

        # set intput filename (first arg) to absolute path from test dir
        warcfile = os.path.join(TEST_DATA_DIR, filename)
        cmdline[0] = warcfile

        cmdline.extend(["--output", str(tmp_path), "--name", filename])

        warc2zim(cmdline)

        zimfile = filename + "_" + time.strftime("%Y-%m") + ".zim"

        if "--progress-file" in cmdline:
            with open(tmp_path / "progress.json", "r") as fh:
                progress = json.load(fh)
                assert (
                    progress["written"] > 0
                    and progress["total"] > 0
                    and progress["written"] <= progress["total"]
                )

        self.verify_warc_and_zim(warcfile, tmp_path / zimfile)

    def test_same_domain_only(self, tmp_path):
        zim_output = "same-domain.zim"
        warc2zim(
            [
                os.path.join(TEST_DATA_DIR, "example-revisit.warc.gz"),
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
            url = article.longurl
            # ignore the replay files, which have only one path segment
            if url.startswith("A/") and len(url.split("/")) > 2:
                assert url.startswith("A/example.com/")

    def test_skip_self_redirect(self, tmp_path):
        zim_output = "self-redir.zim"
        warc2zim(
            [
                os.path.join(TEST_DATA_DIR, "self-redirect.warc"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "self-redir",
            ]
        )

        zim_output = tmp_path / zim_output

        for article in self.list_articles(zim_output):
            url = article.longurl
            if url.startswith("H/"):
                # ensure there is only one H/ record, and its a 200 (not 301)
                assert url == "H/kiwix.org/"
                assert b"HTTP/1.1 200 OK" in self.get_article(
                    zim_output, "H/kiwix.org/"
                )

    def test_include_domains_favicon_and_language(self, tmp_path):
        zim_output = "spt.zim"
        warc2zim(
            [
                os.path.join(TEST_DATA_DIR, "single-page-test.warc"),
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
            url = article.longurl
            # ignore the replay files, which have only one path segment
            if url.startswith("A/") and len(url.split("/")) > 2:
                assert "reseau-canope.fr/" in url

        # test detected language
        assert self.get_article(zim_output, "M/Language") == b"fra"

        # test detected favicon
        favicon = self.get_article_raw(zim_output, "-/favicon")
        assert favicon.is_redirect
        assert (
            favicon.get_redirect_article().longurl
            == "A/lesfondamentaux.reseau-canope.fr/fileadmin/template/img/favicon.ico"
        )

        # test default tags added
        assert (
            self.get_article(zim_output, "M/Tags")
            == b"_ftindex:yes;_category:other;_sw:yes"
        )

    def test_all_warcs_root_dir(self, tmp_path):
        zim_output = "test-all.zim"
        warc2zim(
            [
                os.path.join(TEST_DATA_DIR),
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

        # ensure trailing slash added
        assert b'window.mainUrl = "http://example.com/"' in self.get_article(
            zim_output, "A/index.html"
        )

        # from example.warc.gz
        assert self.get_article(zim_output, "A/example.com/") != b""

        # from single-page-test.warc
        assert (
            self.get_article(
                zim_output, "A/lesfondamentaux.reseau-canope.fr/accueil.html"
            )
            != b""
        )

        # timestamp fuzzy match from example-with-timestamp.warc
        assert self.get_article(zim_output, "H/example.com/path.txt?") != b""

    def test_video_fuzzy_urls(self, tmp_path):
        zim_output = "test-fuzzy.zim"
        warc2zim(
            [
                os.path.join(TEST_DATA_DIR, "video-fuzzy.warc.gz"),
                "--output",
                str(tmp_path),
                "--zim-file",
                zim_output,
                "--name",
                "test-fuzzy",
            ]
        )
        zim_output = tmp_path / zim_output
        res = self.get_article(
            zim_output,
            "H/youtube.fuzzy.replayweb.page/get_video_info?video_id=aT-Up5Y4uRI",
        )
        assert b"Location: " in res

        res = self.get_article(
            zim_output,
            "H/youtube.fuzzy.replayweb.page/videoplayback?id=o-AE3bg3qVNY-gAWwYgL52vgpHKJe9ijdbu2eciNi5Uo_w&itag=18",
        )
        assert b"Location: " in res

    def test_error_bad_replay_viewer_url(self, tmp_path):
        zim_output_not_created = "zim-out-not-created.zim"
        with pytest.raises(Exception) as e:
            warc2zim(
                [
                    "-v",
                    os.path.join(TEST_DATA_DIR, "example-response.warc"),
                    "-r",
                    "x-invalid-x",
                    "--output",
                    str(tmp_path),
                    "--name",
                    "bad",
                    "--zim-file",
                    zim_output_not_created,
                ]
            )

        # zim file should not have been created since replay viewer could not be loaded
        assert not os.path.isfile(zim_output_not_created)

    def test_error_bad_main_page(self, tmp_path):
        zim_output_not_created = "zim-out-not-created.zim"
        with pytest.raises(Exception) as e:
            warc2zim(
                [
                    "-v",
                    os.path.join(TEST_DATA_DIR, "example-response.warc"),
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

    def test_args_only(self):
        # error, name required
        with pytest.raises(SystemExit) as e:
            warc2zim([])
            assert e.code == 2

        # error, no such output directory
        with pytest.raises(Exception) as e:
            warc2zim(["--name", "test", "--output", "/no-such-dir"])

        # success, special error code for no output files
        assert warc2zim(["--name", "test", "--output", "./"]) == 100

    def test_custom_css(self, tmp_path):
        custom_css = b"* { background-color: red; }"
        custom_css_path = tmp_path / "custom.css"
        with open(custom_css_path, "wb") as fh:
            fh.write(custom_css)

        zim_output = "test-css.zim"

        warc2zim(
            [
                os.path.join(TEST_DATA_DIR, "example-response.warc"),
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

        res = self.get_article(zim_output, "A/example.com/")
        assert "https://warc2zim.kiwix.app/custom.css".encode("utf-8") in res

        res = self.get_article(zim_output, "A/warc2zim.kiwix.app/custom.css")
        assert custom_css == res

    def test_custom_css_remote(self, tmp_path):
        zim_output = "test-css.zim"
        url = (
            "https://cdn.jsdelivr.net/npm/bootstrap@4.5.3/dist/css/bootstrap-reboot.css"
        )

        warc2zim(
            [
                os.path.join(TEST_DATA_DIR, "example-response.warc"),
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

        res = self.get_article(zim_output, "A/example.com/")
        assert "https://warc2zim.kiwix.app/custom.css".encode("utf-8") in res

        res = self.get_article(zim_output, "A/warc2zim.kiwix.app/custom.css")
        assert res == requests.get(url).content
