#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" warc2zim conversion utility

This utility provides a conversion from WARC records to ZIM files.
The WARCs are converted in a 'lossless' way, no data from WARC records is lost.
Each WARC record results in two ZIM articles:
- The WARC payload is stored under /A/<url>
- The WARC headers + HTTP headers are stored under the /H/<url>

Given a WARC response record for 'https://example.com/', two ZIM articles are created /A/example.com/ and /H/example.com/ are created.

Only WARC response and resource records are stored.

If the WARC contains multiple entries for the same URL, only the first entry is added, and later entries are ignored. A warning is printed as well.

"""

from argparse import ArgumentParser, RawTextHelpFormatter

from warcio import ArchiveIterator
from libzim.writer import Article, Blob, Creator
import os
import logging
import requests

# Shared logger
logger = logging.getLogger('warc2zim')

DEFAULT_REPLAY_SOURCE_URL = 'https://cdn.jsdelivr.net/npm/replaywebpage/'



# ============================================================================
class BaseArticle(Article):
    """ BaseArticle for all ZIM Articles in warc2zim with default settings
    """
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
class BaseWARCArticle(BaseArticle):
    """ BaseWARCArticle that produces ZIM articles from WARC records
    """
    def __init__(self, record):
        super(BaseWARCArticle, self).__init__()
        self.record = record


# ============================================================================
class WARCHeadersArticle(BaseWARCArticle):
    """ WARCHeadersArticle used to store the WARC + HTTP headers as text
    Usually stored under H namespace
    """
    def __init__(self, record):
        super(WARCHeadersArticle, self).__init__(record)
        self.url = record.rec_headers.get('WARC-Target-URI')

    def get_url(self):
        return 'H/' + self.url.split('//', 2)[1]

    def get_mime_type(self):
        return 'application/warc-headers'

    def get_data(self):
        # add WARC headers
        buff = self.record.rec_headers.to_bytes(encoding='utf-8')
        # add HTTP headers, if present
        if self.record.http_headers:
            buff += self.record.http_headers.to_bytes(encoding='utf-8')

        return Blob(buff)


# ============================================================================
class WARCPayloadArticle(BaseWARCArticle):
    """ WARCPayloadArticle used to store the WARC payload
    Usually stored under A namespace
    """
    def __init__(self, record):
        super(WARCPayloadArticle, self).__init__(record)
        self.payload = record.content_stream().read()
        self.url = record.rec_headers.get('WARC-Target-URI')
        self.mime = self._compute_mime()
        # TODO: converting text/html to application/octet-stream to avoid rewriting by kiwix
        # original mime type still preserved in the headers block
        if self.mime:
            self.mime = self.mime.split(';', 1)[0]
            if self.mime == 'text/html':
                self.mime = 'text/unchanged-html'
        else:
            self.mime = 'application/octet-stream'


    def _compute_mime(self):
        if self.record.http_headers:
        # if the record has HTTP headers, use the Content-Type from those (eg. 'response' record)
            return self.record.http_headers['Content-Type']
        else:
        # otherwise, use the Content-Type from WARC headers
            return self.record.rec_headers['Content-Type']

    def get_url(self):
        return 'A/' + self.url.split('//', 2)[1]

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        return Blob(self.payload)


# ============================================================================
class RWPStaticArticle(BaseArticle):
    def __init__(self, prefix, filename):
        super(RWPStaticArticle, self).__init__()
        self.prefix = prefix
        self.filename = filename

        try:
            resp = requests.get(self.prefix + filename)
            self.content = resp.content
            self.mime = resp.headers.get('Content-Type').split(';')[0]
        except Exception as e:
            logger.error(e)
            logger.error('Unable to load replay system file: {0}'.format(self.prefix + filename))
            raise

    def get_url(self):
        return 'A/' + self.filename

    def get_mime_type(self):
        return self.mime

    def get_data(self):
        return Blob(self.content)


# ============================================================================
class RWPViewerArticle(BaseArticle):
    def __init__(self, filename, main_url):
        super(RWPViewerArticle, self).__init__()
        self.filename = filename
        self.main_url = main_url

    def get_url(self):
        return 'A/' + self.filename

    def get_mime_type(self):
        return 'text/html'

    def get_data(self):
        content = """
<html>
  <head>
    <style>
    body {{
      width: 100%;
      height: 100%;
      overflow-y: hidden;
      margin: 0px;
      padding: 0px;
    }}
    </style>
    <script src="./ui.js"></script>
  </head>
  <body>
    <replay-web-page
     source="proxy:../"
     config='{{"type": "kiwix"}}'
     replayBase="./"
     url="{0}"
     embed="replayonly"
     deepLink="true"
     />
  </body>
</html>
""".format(self.main_url)

        return Blob(content.encode('utf-8'))


# ============================================================================
class WARC2Zim:
    REPLAY_STATIC_FILES = ['index.html', 'ui.js', 'sw.js']

    def __init__(self, args):
        logging.basicConfig(format='[%(levelname)s] %(message)s')
        if args.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        self.indexed_urls = set({})
        self.name = args.name
        if not self.name:
            self.name, ext = os.path.splitext(args.inputs[0])
            self.name += '.zim'

        self.inputs = args.inputs
        self.replay_viewer_source = args.replay_viewer_source
        self.main_url = args.main_url

        self.replay_articles = []
        self.revisits = {}

    def run(self):
        for filename in self.REPLAY_STATIC_FILES:
            self.replay_articles.append(RWPStaticArticle(self.replay_viewer_source, filename))

        with Creator(self.name, main_page='viewer.html', index_language='', min_chunk_size=8192) as zimcreator:
            # add replay system
            for article in self.replay_articles:
                zimcreator.add_article(article)

            zimcreator.add_article(RWPViewerArticle('viewer.html', self.main_url))

            for warcfile in self.inputs:
                self.warc2zim(warcfile, zimcreator)

            # process revisits, headers only
            for url, record in self.revisits.items():
                if url not in self.indexed_urls:
                    logger.debug('Adding revisit {0} -> {1}'.format(url, record.rec_headers['WARC-Refers-To-Target-URI']))
                    zimcreator.add_article(WARCHeadersArticle(record))

    def warc2zim(self, warcfile, zimcreator):
        with open(warcfile, 'rb') as warc_fh:
            for record in ArchiveIterator(warc_fh):
                try:
                    if record.rec_type not in ('resource', 'response', 'revisit'):
                        continue

                    url = record.rec_headers['WARC-Target-URI']
                    if url in self.indexed_urls:
                        logger.warning('Skipping duplicate {0}, already added to ZIM'.format(url))
                        continue

                    if record.rec_type != 'revisit':
                        zimcreator.add_article(WARCHeadersArticle(record))
                        zimcreator.add_article(WARCPayloadArticle(record))
                        self.indexed_urls.add(url)

                    elif record.rec_headers['WARC-Refers-To-Target-URI'] != url and url not in self.revisits:
                        self.revisits[url] = record
                        record.raw_stream = None


                except KeyboardInterrupt:  #pragma: no cover
                    print('Cancelling...')
                    return 1


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

    parser.add_argument('-r', '--replay-viewer-source',
                        help='''URL from which to load the ReplayWeb.page replay viewer from''',
                        default=DEFAULT_REPLAY_SOURCE_URL)

    parser.add_argument('-u', '--main-url',
                        help='''The main url that should be loaded in the viewer on init''')

    parser.add_argument('-o', '--overwrite', action='store_true')

    r = parser.parse_args(args=args)
    warc2zim = WARC2Zim(r)
    return warc2zim.run()


# ============================================================================
def get_version():
    import pkg_resources
    return '%(prog)s ' + pkg_resources.get_distribution('warc2zim').version


# ============================================================================
if __name__ == '__main__':  #pragma: no cover
    warc2zim()


