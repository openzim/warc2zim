#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim conversion utility

This utility provides a conversion from WARC records to ZIM files.
The WARCs are converted in a 'lossless' way, no data from WARC records is lost.
Each WARC record results in two ZIM articles:
- The WARC payload is stored under /A/<url>
- The WARC headers + HTTP headers are stored under the /H/<url>

Given a WARC response record for 'https://example.com/', two ZIM articles are created /A/https://example.com/ and /H/https://example.com/ are created.

Only WARC response and resource records are stored.

If the WARC contains multiple entries for the same URL, only the first entry is added, and later entries are ignored. A warning is printed as well.

"""

from argparse import ArgumentParser, RawTextHelpFormatter

from warcio import ArchiveIterator
from libzim.writer import Article, Blob, Creator
import os
import logging


# ============================================================================
class BaseWARCArticle(Article):
    """ BaseWARCArticle that produces ZIM articles from WARC records
    """
    def __init__(self, record):
        super(BaseWARCArticle, self).__init__()
        self.record = record

    def is_redirect(self):
        return False

    def get_title(self):
        return ''

    def get_filename(self):
        return ''

    def should_compress(self):
        return True

    def should_index(self):
        return False


# ============================================================================
class WARCHeadersArticle(BaseWARCArticle):
    def __init__(self, record):
        super(WARCHeadersArticle, self).__init__(record)
        self.url = record.rec_headers.get('WARC-Target-URI')

    def get_url(self):
        return 'H/' + self.url

    def get_mime_type(self):
        return 'application/warc-headers'

    def get_data(self):
        # add WARC headers
        buff = self.record.rec_headers.to_bytes(encoding='utf-8')
        # add HTTP headers, if present
        if self.record.http_headers:
            buff += self.record.rec_headers.to_bytes(encoding='utf-8')

        return Blob(buff)


# ============================================================================
class WARCPayloadArticle(BaseWARCArticle):
    def __init__(self, record):
        super(WARCPayloadArticle, self).__init__(record)
        self.payload = record.content_stream().read()
        self.url = record.rec_headers.get('WARC-Target-URI')

    def get_url(self):
        return 'A/' + self.url

    def get_mime_type(self):
        if self.record.http_headers:
        # if the record has HTTP headers, use the Content-Type from those (eg. 'response' record)
            return self.record.http_headers['Content-Type']
        else:
        # otherwise, use the Content-Type from WARC headers
            return self.record.rec_headers['Content-Type']

    def get_data(self):
        return Blob(self.payload)


# ============================================================================
class WARC2Zim:
    def __init__(self, args):
        self.logger = logging.getLogger('warc2zim')
        logging.basicConfig(format='[%(levelname)s] %(message)s')
        if args.verbose:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        self.indexed_urls = set({})
        self.name = args.name
        if not self.name:
            self.name, ext = os.path.splitext(args.inputs[0])
            self.name += '.zim'

        self.inputs = args.inputs

    def run(self):
        with Creator(self.name, main_page="index.html", index_language='', min_chunk_size=8192) as zimcreator:
            for warcfile in self.inputs:
                self.warc2zim(warcfile, zimcreator)



    def warc2zim(self, warcfile, zimcreator):
        with open(warcfile, 'rb') as warc_fh:
            for record in ArchiveIterator(warc_fh):
                if record.rec_type != 'resource' and record.rec_type != 'response':
                    continue

                url = record.rec_headers['WARC-Target-URI']
                if url in self.indexed_urls:
                    self.logger.warning('Skipping duplicate {0}, already added to ZIM'.format(url))
                    continue

                zimcreator.add_article(WARCHeadersArticle(record))
                zimcreator.add_article(WARCPayloadArticle(record))

                self.indexed_urls.add(url)


# ============================================================================
def warc2zim(args=None):
    parser = ArgumentParser(description='Create ZIM files from WARC files')

    parser.add_argument('-V', '--version', action='version', version=get_version())
    parser.add_argument('-v', '--verbose', action='store_true')

    parser.add_argument('inputs', nargs='+',
                        help='''Paths of directories and/or files to be included in
                                the WARC file.''')

    parser.add_argument('-n', '--name',
                        help='''Base name for WARC file, appropriate extension will be
                                added automatically.''',
                        metavar='name')

    parser.add_argument('-o', '--overwrite', action='store_true')

    r = parser.parse_args(args=args)
    warc2zim = WARC2Zim(r)
    warc2zim.run()


# ============================================================================
def get_version():
    import pkg_resources
    return '%(prog)s ' + pkg_resources.get_distribution('warc2zim').version


# ============================================================================
if __name__ == '__main__':  #pragma: no cover
    warc2zim()


