## Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (as of version 1.4.0).

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
