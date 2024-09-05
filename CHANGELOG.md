## Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (as of version 1.4.0).

## [2.1.1] - 2024-09-05

### Changed

- Upgrade dependencies, including wombat 3.8.0 (#386)

## [2.1.0] - 2024-08-09

### Added

- New fuzzy-rule for cheatography.com (#342), der-postillon.com (#330), iranwire.com (#363)
- Properly rewrite redirect target url when present in <meta> HTML tag (#237)
- New `--encoding-aliases` argument to pass encoding/charset aliases (#331)
- Add support for SVG favicon (#148)
- Automatically index PDF content and use PDF title (#289 and #290)

### Changed

- Upgrade to python-scraperlib 4.0.0
- Generate fuzzy rules tests in Python and Javascript (#284)
- Refactor HTML rewriter class to make it more open to change and expressive (#305)
- Detect charset in document header only for HTML documents (#331)
- Use `software` property from `warcinfo` record to set ZIM `Scraper` metadata (#357)
- Store `ContentDate` as metadata, based on `WARC-Date` (#358)
- Remove domain specific rules (#328)
- Revisit retrieve_illustration logic to prefer best favicons (#352 and #369)
- Upgrade dependencies (zimscraperlib 4.0.0, wombat.js 3.7.12 and others) (#376)

### Fixed

- Handle case where the redirect target is bad / unsupported (#332 and #356)
- Fixed WARC files handling order to follow creation order (#366)
- Remove subsequent slashes in URLs, both in Python and JS (#365)
- Ignore non HTTP(S) WARC records (#351)
- Fix `vimeo_cdn_fix` fuzzy rule for proper operation in Javascript (#348)
- Performance issue linked to new "extensible" HTML rewriting rules (#370)

## [2.0.3] - 2024-07-24

### Changed

- Moved rules definition from JSON to YAML and documented update process (#216)
- Upgrade to wombat.js 3.7.11

### Added

- Exit with cleaner message when no entries are expected in the ZIM (#336) and when main entry is not processable (#337)
- Add debug log for items whose content is empty (#344)

### Fixed

- Some resources rewrite mode are still not correctly identified (#326)

## [2.0.2] - 2024-06-18

### Added

- Add `--ignore-content-header-charsets` option to disable automatic retrieval of content charsets from content first bytes (#318)
- Add `--content-header-bytes-length` option to specify how many first bytes to consider when searching for content charsets in header (#320)
- Add `--ignore-http-header-charsets` option to disable automatic retrieval of content charsets from content HTTP `Content-Type` headers (#318)

### Changed

- Simplify logic deciding content charset, stop guessing with chardet (#312)

### Fixed

- Rewrite only content with mimetype `text-html` when `WARC-Resource-Type` is `html` (#313)

## [2.0.1] - 2024-06-13

### Added

- Add support for multiple languages in `--lang` CLI argument (#300)

### Changed

- Use the new `WARC-Resource-Type` header to decide rewrite mode (when present in WARC) (#296)
- Upgrade Python dependencies + wombat.js 3.7.5

### Fixed

- Drop `integrity` attribute in HTML `<script>` and `<link>` tags (#298)
- Use automatic detection of content encoding also for JS, JSON and CSS files (#301)
- Set correct charset in HTML documents (#253)

## [2.0.0] - 2024-06-04

### Added

- Allow to specify a scraper suffix for the ZIM scraper metadata at the CLI (#168)
- New test website to test many known situations supposed to be handled (#166)

### Changed

- Replace **Service Worker** approach by **scraper-side rewriting** of static content (https://github.com/kiwix/overview/issues/95)
- Adopted Python bootstrap conventions (#152)
- Upgrade dependencies, especially move to **Python 3.12** (only) and zimscraperlib 3.3.2
- Change wording in logs about the return code 100 (which is not an error code)
- Added checks in `converter.py` to verify output directory existence, logging appropriate error messages and cleanly exit if checks fail. (#106)
- Added check for invalid zim file names (#232)
- Changed default publisher metadata from 'Kiwix' to 'openZIM' (#150)

## [1.5.5] - 2024-01-18

### Changed

- Code restructuration in preparation for 2.x

## [1.5.4] - 2023-09-18

### Changed

- Using wabac.js 2.16.11
- Using `cover` resize method for favicon to prevent issues with too-small ones
- Fixed direct link hack when inside an outer frame (kiwix-serve 3.5+) #119

## [1.5.3] - 2023-08-23

### Changed

- Using wabac.js 2.16.9

## [1.5.2] - 2023-08-02

### Changed

- Using scraperlib 3.1.1, openZIM metatadata now always set, using default if missing
- Using wabac.js 2.16.6

## [1.5.1] - 2023-02-06

### Changed

- Using wabac.js 2.15.2

## [1.5.0] - 2023-02-02

### Added

- Don't crash on failure to convert illustration (skip illus instead)

### Changed

- Fixed 404 page (#96)
- Dont't crash on missing Location headers on potential redirect
- Fixed incorrect ISO-639-3 --lang not replaced with `eng`
- Don't fallback to `eng` if the host doesnt have the matching locale
- Using wabac.js 2.15.0 with fix for scope conflict in SW/DB
- Payload entries now uses original ~`text/html` mimetype instead of `text/html;raw=true`
- dont't crash on icon link with no href

## [1.4.3] - 2022-06-21

### Changed

* Using wabac.js 2.12.0
* Prevent duplicate entries from failing (including illustrations)
* Fixed crash on HTTP 300 records (#94)

## [1.4.0] – 2022-06-14

### Added

* Additional fuzzy matching rules for youtube and vimeo, and additional test cases
* Support for youtube videos, which require POST request handling to work.
* Support for canonicalizing POST request data into URL for fuzzy matching (using cdxj-indexer)
* Support loading custom sw.js from a local file path

### Changed

* Updated zimscraperlib to 1.6 using libzim7.2
* Updated warcio to 1.7.4
* Added support for {period} replacement in --zim-file
* Using fixed MarkupSafe version (Jinja2 dependency)

# [1.3.6]

* updated zimscraperlib (for libzim fix)

# [1.3.5]

* don't crash on records without WARC-Target-URI
* fixed failure if url contains a fragment
* updated wabac.js to 2.7.3

# [1.3.4]

* Added `--custom-css` option

# [1.3.3]

* Added `--progress-file` option

# [1.3.2]

* Update to wabac.js 2.1.6

# [1.3.1]

* Favicon loading fixes: In topFrame.html, load favicon URL directly from ZIM A/ record, bypassing service worker H/ lookup.

# [1.3.0]

* Supports 'fuzzy matching' with additional redirects add from normalized URL to exact URL
* Add fuzzy matching rules for youtube and '?timestamp' URLs
* Fix canonicaliziation where URLs that contain http/https were being incorrectly stripped (https://github.com/openzim/zimit/issues/37)

# [1.2.0]

* Accepts directory inputs as well as individual files. If directory given, which will process all .warc and .warc.gz files recursively in the directory.
* If trailing slash is missing on main URL,  `--url https://example.com?test=value`, slash added and URL treated as `--url https://example.com/?test=value`

# [1.1.0]

* Now defaults to including all URLs unless --include-domains is specifief (removed `-a`)
* Arguments are now checked before starting. Also returns `100` on valid arguments but no WARC provided.

# [1.0.1]

* Now skipping WARC records that redirect to self (http -> https mostly)

# [1.0.0]

* Initial release
