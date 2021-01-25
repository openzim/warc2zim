warc2zim
===

# 1.3.5

* don't crash on records without WARC-Target-URI
* fixed failure if url contains a fragment

# 1.3.4

* Added `--custom-css` option

# 1.3.3

* Added `--progress-file` option

# 1.3.2

* Update to wabac.js 2.1.6

# 1.3.1

* Favicon loading fixes: In topFrame.html, load favicon URL directly from ZIM A/ record, bypassing service worker H/ lookup.

# 1.3.0

* Supports 'fuzzy matching' with additional redirects add from normalized URL to exact URL
* Add fuzzy matching rules for youtube and '?timestamp' URLs
* Fix canonicaliziation where URLs that contain http/https were being incorrectly stripped (https://github.com/openzim/zimit/issues/37)

# 1.2.0

* Accepts directory inputs as well as individual files. If directory given, which will process all .warc and .warc.gz files recursively in the directory.
* If trailing slash is missing on main URL,  `--url https://example.com?test=value`, slash added and URL treated as `--url https://example.com/?test=value`

# 1.1.0

* Now defaults to including all URLs unless --include-domains is specifief (removed `-a`)
* Arguments are now checked before starting. Also returns `100` on valid arguments but no WARC provided.

# 1.0.1

* Now skipping WARC records that redirect to self (http -> https mostly)

# 1.0.0

* Initial release
