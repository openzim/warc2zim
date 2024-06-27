# Technical architecture

## Fuzzy rules

Fuzzy rules are stored in `rules/rules.yaml`. This configuration file is then used by `rules/generateRules.py` to generate Python and JS code.

Should you update these fuzzy rules, you hence have to:
- regenerate Python and JS files by running `python rules/generateRules.py`
- bundle again Javascript `wombatSetup.js` (see below).

## Wombat configuration

Wombat configuration contains some static configuration and the dynamic URL rewriting, including fuzzy rules.

It is bundled by rollup with `cd javascript && yarn build-prod` and the result is pushed to proper scraper location for inclusion at build time.

Tests are available and run with `cd javascript && yarn test`.

## Scraper operations

### High level overview

The scraper behavior is done in two phases.

First the WARC records are iterated to compute the ZIM metadata (find main path, favicon, ...) and detect which ZIM paths are expected to be populated. This is mandatory to know when we will rewrite the documents if the URLs we will encounter leads to something which is internal (inside the ZIM) and should be rewriten or external and should be kept as-is.

Second, the WARC records are iterated to be transformed and appended inside the ZIM. ZIM records are appended to the ZIM on the fly.

In both phases, WARC records are iterated in natural order, i.e. as they have been retrieved online during the crawl.

### Transformation of URL into ZIM path

Transforming a URL into a ZIM path has to respect the ZIM specification: path must not be url-encoded (i.e. it must be decoded) and it must be stored as UTF-8.

WARC record stores the items URL inside a header named "WARC-Target-URI". The value inside this header is encoded, or more exactly it is "exactly what the browser sent at the HTTP level" (see https://github.com/webrecorder/browsertrix-crawler/issues/492 for more details).

It has been decided (by convention) that we will drop the scheme, the port, the username and password from the URL. Headers are also not considered in this computation.

Computation of the ZIM path is hence mostly straightforward:
- decode the hostname which is puny-encoded
- decode the path and query parameter which might be url-encoded

## Rewriting documents

Some documents (HTML, CSS, JS and JSON for now) needs to be rewritten, e.g. to rewrite URLs, adapt some code to the ZIM context, ...

The first important step when processing a WARC entry to add it as a ZIM entry is hence to properly detect which kind of document we are dealing with.

This is done in the `get_rewrite_mode` function of the `Rewriter` class. Before 2.0.1, scraper was relying only on mimetype as returned in `Content-Type` HTTP response.

Unfortunately, this caused problems where some server are returning wrong information is this header, e.g. Cloudflare seems to frequently return `text/html` for woff2 fonts ; this causes the scraper to fail, because it is impossible to know in advance that we should ignore these errors, we could have a real document which should be rewriten but is failing.

Since 2.0.1, we've enriched the logic by using the new WARC header `WARC-Resource-Type` which contains the type of resources "as perceived by the browser" (from https://chromedevtools.github.io/devtools-protocol/tot/Network/#type-ResourceType, see https://github.com/webrecorder/browsertrix-crawler/pull/481). Unfortunately this information is not sufficient because of some very generic value returned like `fetch` or `xhr`. Scraper stills need to mix this information with the mimetype. Ideally, we would have prefer to find a single source of truth not relying on something returned by the server, but it is not available for now (see https://github.com/openzim/warc2zim/issues/340 for a discussion on this topic).

### URL rewriting

In addition to the computation of the relative path from the current document URL to the URL to rewrite, URL rewriting also consists in computing the proper ZIM path (with same operation as above) and properly encoding it so that the resulting URL respects [RFC 3986](https://datatracker.ietf.org/doc/html/rfc3986). Some important stuff has to be noted in this encoding.

- since the original hostname is now part of the path, it will now be url-encoded
- since the `?` and following query parameters are also part of the path (we do not want readers to drop them like kiwix-serve would do), they are also url-encoded

Below is an example case of the rewrite operation on an image URL found in an HTML document.

- Document original URL: `https://kiwix.org/a/article/document.html`
- Document ZIM path: `kiwix.org/a/article/document.html`
- Image original URL: `//xn--exmple-cva.com/a/resource/image.png?foo=bar`
- Image rewritten URL: `../../../ex%C3%A9mple.com/a/resource/image.png%3Ffoo%3Dbar`
- Image ZIM Path: `exémple.com/a/resource/image.png?foo=bar`

### JS Rewriting

JS Rewriting is a bit special because rules to apply are different wether we are using "classic" Javascript or "module" Javascript.

Detection of Javascript modules starts at the HTML level where we have a `<script type="module"  src="...">` tag. This tells us that file at src location is a Javascript module. From there we now that its subresources are also Javascript module.

Currently this detection is done on-the-fly, based on the fact that WARC items are processed in the same order that they have been fetched by the browser, and we hence do not need a multi-pass approach. Meaning that HTML will be processed first, then parent JS, then its dependencies, ... **This is a strong assumption**.

### Different kinds of WARC records

The WARC to ZIM conversion is performed by transforming WARC records into ZIM records.

For `response` records, the rewritten payload (only, without HTTP headers) is stored inside the ZIM.

If the payload is zero-length, the record is omitted to conform to ZIM specifications of not storing empty records.

For `request` and `resource` records, they are simply ignored. These records do not convey important information for now.

**TODO** better explain what `request` and `resource` records are and why they might point to a different URL.

For `revisit` records, a ZIM alias is created if the revisit points to a diferrent URL.

**TODO** better explain what `revisit` records are and why they might point to a different URL.

### Duplicate URIs

WARCs allow multiple records for the same URL, while ZIM does not. As a result, only the first encountered response or resource record is stored in the ZIM, and subsequent records are ignored.

For revisit records, they are only added as a ZIM alias if pointing to a different URL, and are processed after response records. A revisit record to the same URL will always be ignored.

All other WARC records are skipped.
