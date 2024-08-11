# warc2zim

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/warc2zim/badge)](https://www.codefactor.io/repository/github/openzim/warc2zim)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![codecov](https://codecov.io/gh/openzim/warc2zim/branch/main/graph/badge.svg)](https://codecov.io/gh/openzim/warc2zim)
[![PyPI - Package version](https://img.shields.io/pypi/v/warc2zim.svg)](https://pypi.org/project/warc2zim)
[![PyPI - Supported Python versions](https://img.shields.io/pypi/pyversions/warc2zim.svg)](https://pypi.org/project/warc2zim)


warc2zim converts WARC files to ZIM file. The resulting ZIM contains all WARC records, with "programming" records (HTML/CSS/JS/...) rewriten for proper offline operation.

The resulting ZIM is self-contained and can render properly in offline situations.

Since warc2zim 2.0.0, service workers and HTTPs are not needed anymore for proper ZIM rendering (this was a big constraint of ZIM produced by warc2zim 1.x).

WARC format being an archive of any website property, warc2zim is the perfect companion to turn any website into an offline content (see e.g. https://www.github.com/openzim/zimit for a scraper bundling the approach, transform a website URL into an offline ZIM content in a single command).

## Capabilities

While we would like to support as many websites as possible, making an offline archive of a website obviously has some limitations.

Scenario which are known to work well:
- HTML and CSS documents
- JS manipulating the DOM and/or doing simple fetch (preferably GET) requests
  - E.g. JS manipulating the DOM to modify images, fetch remote stuff (JSON data, ...) is supposed to work
  - POST requests support is fairly limited (at best, scraper replays the same response as it has been recorded)
- Puny-encoded hostnames
- Encoded URL path
- URL query string
- URL fragments
- JS modules
- HTML base href
- Youtube embedded video player

## Known limitations

- Any web site expecting a server to store live data and wanting to modifying those data (form, read/write api, ...) is not supported
- Except Youtube embedded video player, most video players (Vimeo, DailyMotion, ...) are either not working or needing advanced tuning
- Website using dynamic resources (dynamic URLs) fetch based on user-agent configuration (e.g. viewport), timestamp, unique ID
  - E.g. if the viewport size is sent in every requests to fetch website images, this will not work since the URL built during the scrape will most likely be different than the URL built when the end-user read the ZIM content, and the ZIM reader won't find associated resource
  - Scraper tries to do its best on few popular websites (e.g. Youtube embedded player) by getting rid of dynamic parts in URL during URL rewriting (with what is called fuzzy rules), but support is fairly very limited
- For simplification, scraper assumes that:
  - servers do not mix multiple ports with two different resources at same hostname and path. E.g. if `http://www.acme.com:80/resource1` and `http://www.acme.com:8080/resource1` both exist AND lead to different resources, the scraper will include in the ZIM only the first resource fetched and silently ignore all other resources in conflict
  - corollary: servers do not mix HTTP and HTTPS with two different resources at same hostname and path. E.g. if `http://www.acme.com/resource1` and `https://www.acme.com/resource1` both exist AND lead to different resources, the scraper will include in the ZIM only the first resource fetched and silently ignore all other resources in conflict
- Scraper does not store HTTP response headers: these headers are not stored inside the ZIM / not replayed ; any website requiring these will be broken
  - Files with a `Content-Disposition: attachment` response header are expected to be automatically saved by the browser. This does not happen for now (see https://github.com/openzim/warc2zim/issues/288).
- Scraper does not take into account HTTP request headers: if different request header values leads to two different page / resource, scraper is ignoring this information
- User-Agent: corollary of the point above on HTTP request headers, scraper supposes a single User-Agent has been used to create the WARC files ; if the website is providing different content based on the User-Agent, only one will be used
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
- HTTP/2 support is working but limited to same limitations mentioned above
- HTML/JS importmaps are not yet supported (see https://github.com/openzim/warc2zim/issues/230)
- Redirections with `meta http-equiv` are not yet supported (see https://github.com/openzim/warc2zim/issues/237)
- Web workers are not yet supported (see https://github.com/openzim/warc2zim/issues/272)
- Service workers are not supported and will most probably never be
- Inline JS code inside an onxxx HTML event (e.g. onclick, onhover, ...) is rewritten, so for instance redirection to another handled with these events is working
  - However since URL rewriting is performed with dynamic JS rewriting, at this stage scraper has no clue on what is inside the ZIM and what is external ; all URLs are hence supposed to be internal, which might break some dynamic redirection to an online website

It is also important to note that warc2zim is inherently limited to what is present inside the WARC. A bad WARC can only produce a bad ZIM. Garbage in, garbage out.

It is hence very important to properly configure the system used to create the WARC. If zimit is used (and hence WebRecorder Browsertrix crawler), it is very important to properly configure scope type, mobile device used, behaviors (including custom ones needed on some sites) and login profile.

Adding a custom CSS is also strongly recommended to hide features which won't work offline (e.g. search box which relies on a live search server).

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

### Failed items

When an item fails to be converted into the ZIM and `--verbose` flag is passed, the failed item content is stored on the filesystem for easier analysis. The directory where this file is saved can be customized with `--failed-items`. File name is a random UUID4 which is output in the logs.

### Development features

For developement purpose, it is possible to ask to continue on WARC record processing errors with `--continue-on-error`.

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
