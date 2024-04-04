#!/bin/bash

# Replace all occurences of accentuated_hostname in html files

find /var/www/html -type f -name '*.html' -exec sed -i "s/https:\/\/accentuated_hostname/$ACCENTUATED_HOSTNAME/g" {} \;
find /var/www/html -type f -name '*.html' -exec sed -i "s/https:\/\/standard_hostname/$STANDARD_HOSTNAME/g" {} \;

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
