# Software architecture

## cdxj_indexer and warcio

[cdxj_indexer Python library](https://pypi.org/project/cdxj-indexer/) is a thin wrapper over [warcio Python library](https://pypi.org/project/warcio/). It used to iterate all record in WARCs.

It provide two main features:

- Loop over several WARCs in a directory (A visit of a website may be stored in several WARCs in the same directory).
- Provide a buffered access to warcs content (and not a "stream" (fileio) only api) (but monkey patching returned WarcRecord.

Except that, scraper directly uses WarcRecord (returned by cdxj_indexer, implemented in warcio) to access metadata and such.

cdxj_indexer usefull methods are currently forked in warc2zim, see https://github.com/openzim/warc2zim/pull/428 for details.

## zimscraperlib

[zimscraperlib Python library](https://pypi.org/project/zimscraperlib) is used for ZIM operations and for all HTML / CSS / JS rewriting operations (mostly around URL manipulations, but not only).

## requests

[requests Python library](https://pypi.org/project/requests/) is used to retrieve the custom CSS file when a URL is passed.

## brotlipy

[brotlipy Python library](https://pypi.org/project/brotlipy/) is used to access brotli content in WARC records (not part of warcio because it is an optional dependency).
