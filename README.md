# warc2zim

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/warc2zim/badge)](https://www.codefactor.io/repository/github/openzim/warc2zim)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![codecov](https://codecov.io/gh/openzim/warc2zim/branch/main/graph/badge.svg)](https://codecov.io/gh/openzim/warc2zim)
[![PyPI - Package version](https://img.shields.io/pypi/v/warc2zim.svg)](https://pypi.org/project/warc2zim)
[![PyPI - Supported Python versions](https://img.shields.io/pypi/pyversions/warc2zim.svg)](https://pypi.org/project/warc2zim)


warc2zim provides a way to convert WARC files to ZIM, storing the WARC payload and WARC+HTTP headers separately.

Additionally, the [ReplayWeb.page](https://replayweb.page) is also added to the ZIM, creating a self-contained ZIM
that can render its content in a modern browser.

## Usage

Example:

```
warc2zim ./path/to/myarchive.warc --output /output --name myarchive.zim -u https://example.com/
```

The above will create a ZIM file `/output/myarchive.zim` with `https://example.com/` set as the main page.

## Installation

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

By default, all URLs found in the WARC files are included unless the `--include-domains`/ `-i` flag is set.

To filter URLs that may be out of scope (eg. ads, social media trackers), use the `--include-domains`/ `-i` flag to specify each domain you want to include.

Other URLs will be filtered and not pushed to the ZIM.

Note that the domain passed **and all its subdomains** are included.

Eg. if main page is on a subdomain `https://subdomain.example.com/` but all URLs from `*.example.com` should be included, use:

```
warc2zim myarchive.warc --name myarchive -i example.com -u https://subdomain.example.com/starting/page.html
```

If main page is on a subdomain, `https://subdomain.example.com/` and only URLs from `subdomain.example.com` should be included, use:

```
warc2zim myarchive.warc --name myarchive -i subdomain.example.com -u https://subdomain.example.com/starting/page.html
```

If main page is on a subdomain, `https://subdomain1.example.com/` and only URLs from `subdomain1.example.com` and `subdomain2.example.com` should be included, use:

```
warc2zim myarchive.warc --name myarchive -i subdomain1.example.com -i subdomain2.example.com -u https://subdomain1.example.com/starting/page.html
```

## Custom CSS

`--custom-css` allows passing an URL or a path to a CSS file that gets added to the ZIM and gets included on **every HTML article** at the very end of `</head>` (if it exists).


See `warc2zim -h` for other options.


## ZIM Entry Layout

The WARC to ZIM conversion is performed by splitting the WARC (and HTTP) headers from the payload.

For `response` records, the WARC + HTTP headers are stored under `H/<url>` while the payload is stored under `A/<url>`

For `resource` records, the WARC headers are stored under `H/<url>` while the payload is stored under `A/<url>`. (Three are no HTTP headers for resource records).

For `revisit` records, the WARC + optional HTTP headers are stored under `H/<url>`, while no payload record is created.


If the payload `A/<url>` is zero-length, the record is omitted to conform to ZIM specifications of not storing empty records.


## Duplicate URIs

WARCs allow multiple records for the same URL, while ZIM does not. As a result, only the first encountered response or resource record is stored in the ZIM,
and subsequent records are ignored.

For revisit records, they are only added if pointing to a different URL, and are processed after response/revisit records. A revisit record to the same URL
will always be ignored.

All other WARC records are skipped.

## Contributing

First, clone this repository.

If you do not already have it on your system, install hatch to build the software and manage virtual environments (you might be interested by our detailed [Developer Setup](https://github.com/openzim/_python-bootstrap/wiki/Developer-Setup) as well).

```bash
pip3 install hatch
```

Start a hatch shell: this will install software including dependencies in an isolated virtual environment.

```bash
hatch shell
```

## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0) or later, see
[LICENSE](LICENSE) for more details.
