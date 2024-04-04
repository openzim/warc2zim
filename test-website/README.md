# Test website

This is a test website for zimit / warc2zim tests.

It contains all kind of situations we currently cope with:
- a youtube player
- a vimeo player
- an X/twitter post
- an X/twitter video
- a facebook video
- a facebook post
- an instagram embed

- invalid inline CSS
- invalid rule in a CSS file


## How to use locally

Build the docker image

```
docker build -t test-website .
```

Start the test website with appropriate environment variables.

```
docker run -p 8888:80 --rm --name test-website -e SITE_ADDRESS="test-website.local.oviles.info:80, xn--jdacents-v0aqb.local.oviles.info:80" -e STANDARD_HOSTNAME="http:\/\/test-website.local.oviles.info:8888" -e ACCENTUATED_HOSTNAME="http:\/\/jédéacçents.local.oviles.info:8888" test-website
```

In the example above, the trick is that we have the following DNS records in place : `local.oviles.info A 127.0.0.1` and `*.local.oviles.info CNAME local.oviles.info`, meaning that any request to local.oviles.info or one of its subdomain will resolve to localhost IP 127.0.0.1 ; we use local ports 8080 for HTTP and 8443 for HTTPS.

You can then open https://test-website.local.oviles.info:8888 in your favorite browser and run manual tests on this website (which uses the other one as sub-site for few resources on special domains with special characters).

## Environments variables needed in Docker image

- SITE_ADDRESS: the site address for Caddy operation ; should contain a non-accentuated and an accentuated hostnames for proper testing
- STANDARD_HOSTNAME: the full hostname to the non-accentuated / standard hostname as seen from the browser (will be used in HTML/JS/... files) ; will be used by `sed` as replacement, so few chars (e.g. `/`) must be escaped
- ACCENTUATED_HOSTNAME: the full hostname to the accentuated hostname as seen from the browser (will be used in HTML/JS/... files) ; will be used by `sed` as replacement, so few chars (e.g. `/`) must be escaped
