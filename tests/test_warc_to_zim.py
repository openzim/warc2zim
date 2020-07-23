from warc2zim.main import warc2zim
import tempfile
import shutil
import os
import pytest

from io import BytesIO

import libzim.reader
from warcio import ArchiveIterator


WARCS = ['example-response.warc', 'example-resource.warc.gz', 'example-utf8.warc', 'netpreserve-twitter.warc']

@pytest.fixture(params=WARCS)
def filename(request):
    return request.param



# ============================================================================
class TestWarc2Zim(object):
    @classmethod
    def setup_class(cls):
        cls.root_dir = os.path.realpath(tempfile.mkdtemp())
        cls.orig_cwd = os.getcwd()
        os.chdir(cls.root_dir)

        cls.test_data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')

    @classmethod
    def teardown_class(cls):
        os.chdir(cls.orig_cwd)
        shutil.rmtree(cls.root_dir)

    def verify_warc_and_zim(self, warcfile, zimfile):
        assert os.path.isfile(warcfile)
        assert os.path.isfile(zimfile)

        # track to avoid checking duplicates, which are not written to ZIM
        warc_urls = set()

        zim_fh = libzim.reader.File(zimfile)
        with open(warcfile, 'rb') as warc_fh:
            for record in ArchiveIterator(warc_fh):
                url = record.rec_headers['WARC-Target-URI']
                if not url:
                    continue

                if url in warc_urls:
                    continue

                if record.rec_type not in (('response', 'resource', 'revisit')):
                    continue

                # ignore revisit records that are to the same url
                if record.rec_type == 'revisit' and record.rec_headers['WARC-Refers-To-Target-URI'] == url:
                    continue

                # parse headers as record, ensure headers match
                headers = zim_fh.get_article('H/' + url)
                parsed_record = next(ArchiveIterator(BytesIO(headers.content.tobytes())))

                assert record.rec_headers == parsed_record.rec_headers
                assert record.http_headers == parsed_record.http_headers

                # ensure payloads match
                payload = zim_fh.get_article('A/' + url)

                if record.rec_type == 'revisit':
                    assert payload == None
                else:
                    assert payload.content.tobytes() == record.content_stream().read()

                warc_urls.add(url)

    def test_warc_to_zim_specify_output(self):
        zim_output = os.path.join(self.root_dir, 'zim-out-filename.zim')
        warc2zim(['-v', os.path.join(self.test_data_dir, 'example-response.warc'), '-n', zim_output])

        assert os.path.isfile(zim_output)

    def test_warc_to_zim(self, filename):
        warcfile = os.path.join(self.root_dir, filename)

        # copy test WARCs to test dir to test different output scenarios
        shutil.copy(os.path.join(self.test_data_dir, filename), warcfile)

        warc2zim([warcfile])

        zimfile, ext = os.path.splitext(warcfile)
        zimfile += '.zim'

        self.verify_warc_and_zim(warcfile, zimfile)

    def test_error_bad_replay_viewer_url(self):
        zim_output = os.path.join(self.root_dir, 'zim-out-filename.zim')
        with pytest.raises(Exception) as e:
            warc2zim(['-v', os.path.join(self.test_data_dir, 'example-response.warc'), '-r', 'x-invalid-x'])


