# warc2zim
[![](https://img.shields.io/pypi/v/warc2zim.svg)](https://pypi.python.org/pypi/warc2zim)
![CI](https://github.com/openzim/warc2zim/workflows/CI/badge.svg)
[![codecov](https://codecov.io/gh/openzim/warc2zim/branch/main/graph/badge.svg)](https://codecov.io/gh/openzim/warc2zim)
[![CodeFactor](https://www.codefactor.io/repository/github/openzim/warc2zim/badge)](https://www.codefactor.io/repository/github/openzim/warc2zim)

warc2zim provides a way to convert WARC files to ZIM, storing the WARC payload and WARC+HTTP headers separately.

Additionally, the [ReplayWeb.page](https://replayweb.page) is also added to the ZIM, creating a self-contained ZIM
that can render its content in a modern browser.

## Usage

Example:

```
warc2zim ./path/to/myarchive.warc --output /output --name myarchive.zim -u https://example.com/
```

The above will create a ZIM file `/output/myarchive.zim` with `https://example.com/` set as the main page.

### Installation

```sh
python3 -m venv ./env  # creates a virtual python environment in ./env folder
./env/bin/pip install -U pip  # upgrade pip (package manager). recommended
./env/bin/pip install -U warc2zim  # install/upgrade warc2zim inside virtualenv

# direct access to in-virtualenv warc2zim binary, without shell-attachment
./env/bin/warc2zim --help

# alternatively, attach virtualenv to shell
source env/bin/activate
warc2zim --help
deactivate  # unloads virtualenv from shell
```

## URL Filtering

By default, only URLs from domain of the main page and subdomains are included, eg. only `*.example.com` urls in the above example.

This allows for filtering out URLs that may be out of scope (eg. ads, social media trackers).

To specify a different top-level domain, use the `--include-domains`/ `-i` flag for each domain, eg. if main page is on a subdomain, `https://subdomain.example.com/` but all URLs from `*.example.com` should be included, use:


```
warc2zim myarchive.warc --name myarchive -i example.com -u https://subdomain.example.com/starting/page.html
```


To simply include all urls, use the `--include-all` / `-a` flag:

```
warc2zim myarchive.warc --name myarchive -a -u https://someother.example.com/page.html
```

### Custom CSS

`--custom-css` allows passing an URL or a path to a CSS file that gets added to the ZIM and gets included on **every HTML article** at the very end of `</head>` (if it exists).


See `warc2zim -h` for other options.


## ZIM Entry Layout

The WARC to ZIM conversion is performed by splitting the WARC (and HTTP) headers from the payload.

For `response` records, the WARC + HTTP headers are stored under `H/<url>` while the payload is stored under `A/<url>`

For `resource` records, the WARC headers are stored under `H/<url>` while the payload is stored under `A/<url>`. (Three are no HTTP headers for resource records).

For `revisit` records, the WARC + optional HTTP headers are stored under `H/<url>`, while no payload record is created.


If the payload `A/<url>` is zero-length, the record is omitted to conform to ZIM specifications of not storing empty records.


### Duplicate URIs

WARCs allow multiple records for the same URL, while ZIM does not. As a result, only the first encountered response or resource record is stored in the ZIM,
and subsequent records are ignored.

For revisit records, they are only added if pointing to a different URL, and are processed after response/revisit records. A revisit record to the same URL
will always be ignored.

All other WARC records are skipped.

## i18n

`warc2zim` has very minimal non-content text but still uses gettext through [babel](http://babel.pocoo.org/en/latest/setup.html) to internationalize.

To add a new locale (`fr` in this example, use only ISO-639-1):

1. init for your locale: `python setup.py init_catalog -l fr`
2. make sure the POT is up to date `python setup.py extract_messages`
3. update your locale's catalog `python setup.py update_catalog`
3. translate the PO file ([poedit](https://poedit.net/) is your friend)
4. compile updated translation `python setup.py compile_catalog`

## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0) or later, see
[LICENSE](LICENSE) for more details.
