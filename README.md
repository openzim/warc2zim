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

## Usage

### URL Filtering

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

### Custom CSS

`--custom-css` allows passing an URL or a path to a CSS file that gets added to the ZIM and gets included on **every HTML article** at the very end of `</head>` (if it exists).

### Other options

See `warc2zim -h` for other options.

## Documentation

We have documentation about the [functional architecture](docs/functional_architecture.md), the [technical architecture](docs/technical_architecture.md) and the [software architecture](docs/software_architecture.md).

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
