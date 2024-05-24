#!/bin/bash

# Reverse the modifications done by entrypoint.sh ; usefull for local development when local directory is mounted inside the container
# for rapid tests but the modifications have to be reversed so that proper stuff is commited in Github

find /var/www/html -type f -exec sed -i 's/http:\/\/jédéacçents.local.oviles.info:8888/https:\/\/not_standard_netloc_not_encoded/g' {} \;
find /var/www/html -type f -exec sed -i 's/http:\/\/xn--jdacents-v0aqb.local.oviles.info:8888/https:\/\/not_standard_netloc_punny_encoded/g' {} \;
find /var/www/html -type f -exec sed -i 's/http:\/\/test-website.local.oviles.info:8888/https:\/\/standard_netloc/g' {} \;
