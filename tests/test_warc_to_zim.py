import tempfile
import shutil
import os
from io import BytesIO

import pytest

import libzim.reader
from warcio import ArchiveIterator

from warc2zim.main import warc2zim


CMDLINES = [
    ["example-response.warc"],
    ["example-resource.warc.gz"],
    ["example-revisit.warc.gz", "-a"],
    ["example-utf8.warc", "-u", "https://httpbin.org/anything/utf8=%E2%9C%93?query=test&a=b&1=%E2%9C%93"],
    ["netpreserve-twitter.warc", "-a"]
]


@pytest.fixture(params=CMDLINES)
def cmdline(request):
    return request.param


# ============================================================================
class TestWarc2Zim(object):
    @classmethod
    def setup_class(cls):
        cls.root_dir = os.path.realpath(tempfile.mkdtemp())
        cls.orig_cwd = os.getcwd()
        os.chdir(cls.root_dir)

        cls.test_data_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "data"
        )

    @classmethod
    def teardown_class(cls):
        os.chdir(cls.orig_cwd)
        shutil.rmtree(cls.root_dir)

    def list_articles(self, zimfile):
        zim_fh = libzim.reader.File(zimfile)
        for x in range(zim_fh.article_count):
            yield zim_fh.get_article_by_id(x)

    def get_article(self, zimfile, path):
        zim_fh = libzim.reader.File(zimfile)
        return zim_fh.get_article(path).content.tobytes()

    def verify_warc_and_zim(self, warcfile, zimfile):
        assert os.path.isfile(warcfile)
        assert os.path.isfile(zimfile)

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
                    assert payload == None
                else:
                    assert payload.content.tobytes() == record.content_stream().read()

                warc_urls.add(url)

    def test_warc_to_zim_specify_params_and_metadata(self):
        zim_output = os.path.join(self.root_dir, "zim-out-filename.zim")
        warc2zim(
            [
                "-v",
                os.path.join(self.test_data_dir, "example-response.warc"),
                "-o",
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
            ]
        )

        assert os.path.isfile(zim_output)

        all_articles = {
            article.longurl: article.title for article in self.list_articles(zim_output)
        }

        assert all_articles == {
            # entries from WARC
            "A/example.com/": "Example Domain",
            "H/example.com/": "http://example.com/",
            # replay system files
            "A/index.html": "index.html",
            "A/load.js": "load.js",
            "A/notFoundPage.html": "notFoundPage.html",
            "A/sw.js": "sw.js",
            "A/topFrame.html": "topFrame.html",
            # ZIM metadata
            "M/Counter": "Counter",
            "M/Creator": "Creator",
            "M/Date": "Date",
            "M/Description": "Description",
            "M/Flavour": "Flavour",
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
        assert self.get_article(zim_output, "M/Tags") == b"some;foo;bar"

    def test_warc_to_zim(self, cmdline):
        filename = cmdline[0]
        warcfile = os.path.join(self.root_dir, filename)

        # copy test WARCs to test dir to test different output scenarios
        shutil.copy(os.path.join(self.test_data_dir, filename), warcfile)

        warc2zim([warcfile] + cmdline[1:])

        zimfile, ext = os.path.splitext(warcfile)
        zimfile += ".zim"

        self.verify_warc_and_zim(warcfile, zimfile)

    def test_error_bad_replay_viewer_url(self):
        zim_output_not_created = os.path.join(self.root_dir, "zim-out-not-created.zim")
        with pytest.raises(Exception) as e:
            warc2zim(
                [
                    "-v",
                    os.path.join(self.test_data_dir, "example-response.warc"),
                    "-r",
                    "x-invalid-x",
                    "-o",
                    zim_output_not_created,
                ]
            )

        # zim file should not have been created since replay viewer could not be loaded
        assert not os.path.isfile(zim_output_not_created)
