#!/bin/bash

# Replace all occurences of hostnames in html files

find /var/www/html -type f -exec sed -i "s/https:\/\/not_standard_netloc_not_encoded/$NOT_STANDARD_NETLOC_NOT_ENCODED/g" {} \;
find /var/www/html -type f -exec sed -i "s/https:\/\/not_standard_netloc_punny_encoded/$NOT_STANDARD_NETLOC_PUNNY_ENCODED/g" {} \;
find /var/www/html -type f -exec sed -i "s/https:\/\/standard_netloc/$STANDARD_NETLOC/g" {} \;

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
