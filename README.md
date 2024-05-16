# warc2zim

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/warc2zim/badge)](https://www.codefactor.io/repository/github/openzim/warc2zim)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![codecov](https://codecov.io/gh/openzim/warc2zim/branch/main/graph/badge.svg)](https://codecov.io/gh/openzim/warc2zim)
[![PyPI - Package version](https://img.shields.io/pypi/v/warc2zim.svg)](https://pypi.org/project/warc2zim)
[![PyPI - Supported Python versions](https://img.shields.io/pypi/pyversions/warc2zim.svg)](https://pypi.org/project/warc2zim)


warc2zim provides a way to convert WARC files to ZIM, storing the WARC payload and WARC+HTTP headers separately.

Additionally, the [ReplayWeb.page](https://replayweb.page) is also added to the ZIM, creating a self-contained ZIM
that can render its content in a modern browser.

## Known limitations

- HTTP return codes have known limitations:
  - in the `2xx` range, only `200`, `201`, `202` and `203` are supported ; others are simply ignored
  - in the `3xx` range, only `301`, `302`, `306` and `307` are supported if they redirect to a payload which is present in the WARC ; others are simply ignored
  - all payloads with HTTP return codes in the `1xx` (not supposed to exist in WARC files anyway), `4xx` and `5xx` ranges are ignored
- HTML documents are always interpreted since we have to rewrite all URLs as well as inline documents (JS, CSS). This has some side-effects even if we try to minimize them.
  - HTML tag attributes values are always surrounded by double quotes in the ZIM HTML documents
  - HTML tag attributes are always unescaped from any named or numeric character references (e.g. &gt;, &#62;, &#x3e;) for proper processing when they have to be adapted. Only mandatorily escaped characters (`&`, `<`, `>`, `'` and `"`) are escaped-back.
    - Numeric character references are replaced by their named character references equivalence
    - Named character references are always lower-cased
    - This processing has some bad side-effects when attribute values were not escaped in the original HTML document. E.g. `<img src="image.png?param1=value1&param2=value2">` is transformed into `<img src="image.png%3Fparam1%3Dvalue1%C2%B6m2%3Dvalue2">` because URL was supposed to be `image.png?param1=value1¶m2=value2` because `&para` has been decoded to `¶`. HTML should have been `<img src="image.png?param1=value1&amp;param2=value2">` for the URL to be `image.png?param1=value1&param2=value2`
    - See https://github.com/openzim/warc2zim/issues/219 for more discussions / details / pointers

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

Requirements:
- proper Python version (see pyproject.toml) with pip
- optionally Docker
- optionally Node LTS version (20 recommended)

First, clone this repository.

If you do not already have it on your system, install hatch to build the software and manage virtual environments (you might be interested by our detailed [Developer Setup](https://github.com/openzim/_python-bootstrap/wiki/Developer-Setup) as well).

```bash
pip3 install hatch
```

Start a hatch shell: this will install software including dependencies in an isolated virtual environment.

```bash
hatch shell
```

### Regenerate wombatSetup.js

wombatSetup.js is the JS code used to setup wombat when the ZIM is used.

It is normally retrieved by Python build process (see openzim.toml for details).

Recommended solution to develop this JS code is to install Node.JS on your system, and then

```bash
cd javascript
yarn build-dev # or yarn build-prod
```

Should you want to regenerate this code without install Node.JS, you might simply run following command.

```bash
docker run -v $PWD/src/warc2zim/statics:/output -v $PWD/rules:/src/rules -v $PWD/javascript:/src/javascript -v $PWD/build_js.sh:/src/build_js.sh -it --rm --entrypoint /src/build_js.sh node:20-bookworm
```

It will install Python3 on-top of Node.JS in a Docker container, generate JS fuzzy rules and bundle JS code straight to `/src/warc2zim/statics/wombatSetup.js` where the file is expected to be placed.

## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0) or later, see
[LICENSE](LICENSE) for more details.
