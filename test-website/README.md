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
docker run -p 8888:80 --rm --name test-website -e SITE_ADDRESS="test-website.local.oviles.info:80, xn--jdacents-v0aqb.local.oviles.info:80" -e STANDARD_NETLOC="http:\/\/test-website.local.oviles.info:8888" -e NOT_STANDARD_NETLOC_NOT_ENCODED="http:\/\/jédéacçents.local.oviles.info:8888" -e NOT_STANDARD_NETLOC_PUNNY_ENCODED="http:\/\/xn--jdacents-v0aqb.local.oviles.info:8888" test-website
```

In the example above, the trick is that we have the following DNS records in place : `local.oviles.info A 127.0.0.1` and `*.local.oviles.info CNAME local.oviles.info`, meaning that any request to local.oviles.info or one of its subdomain will resolve to localhost IP 127.0.0.1 ; we use local ports 8080 for HTTP and 8443 for HTTPS.

You can then open https://test-website.local.oviles.info:8888 in your favorite browser and run manual tests on this website (which uses the other one as sub-site for few resources on special domains with special characters).

If you wanna develop the test-website locally, you might want as well to mount the `content` folder inside the container

```
docker run -v $PWD/content:/var/www/html -p 8888:80 --rm --name test-website -e SITE_ADDRESS="test-website.local.oviles.info:80, xn--jdacents-v0aqb.local.oviles.info:80" -e STANDARD_NETLOC="http:\/\/test-website.local.oviles.info:8888" -e NOT_STANDARD_NETLOC_NOT_ENCODED="http:\/\/jédéacçents.local.oviles.info:8888" -e NOT_STANDARD_NETLOC_PUNNY_ENCODED="http:\/\/xn--jdacents-v0aqb.local.oviles.info:8888" test-website
```

This will have the adverse effect that local files will be modified as well by the `entrypoint.sh` to replace placeholders by environment variables value. And it means that you have to use "real" netloc from the environment in your modifications for test.

Once done, there is a utility script at `entrypoint-reverse.sh` which can be used to reverse these modifications once you are about to commit to Github (this will break the test-website inside Docker container, but you will be able to commit with proper modifications and then just restart the container to reapply needed modification).

## Environments variables needed in Docker image

|Environment variable | Usage | Comment | Sample value |
|--|--|--|--|
| `SITE_ADDRESS` | Caddyfile | The site address for Caddy operation ; should contain a standard and a not-standard punny-encoded hostnames for proper testing | `test-website.local.oviles.info:80, xn--jdacents-v0aqb.local.oviles.info:80` |
| `STANDARD_NETLOC` | sed in HTML/JS/... files ^1 | The URL to the standard netloc (no special characters) | `http:\/\/test-website.local.oviles.info:8888` |
| `NOT_STANDARD_NETLOC_NOT_ENCODED` | sed in HTML/JS/... files ^1 | The URL to the not standard netloc (with special characters) but not encoded | `http:\/\/jédéacçents.local.oviles.info:8888` |
| `NOT_STANDARD_NETLOC_PUNNY_ENCODED` | sed in HTML/JS/... files ^1 | The URL to the not standard netloc (with special characters) punny encoded | `http:\/\/xn--jdacents-v0aqb.local.oviles.info:8888` |

1. variables that will be used by `sed` as replacement have to be be escaped for proper sed operations ; since they will be interpreted by the browser, they should contain the "user-visible" FQDN and port
