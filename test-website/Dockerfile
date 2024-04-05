FROM caddy:2.6.1-alpine
LABEL org.opencontainers.image.source https://github.com/openzim/warc2zim

COPY Caddyfile /etc/caddy/Caddyfile

COPY content/ /var/www/html/

RUN apk add --no-cache bash

COPY entrypoint.sh /root/entrypoint.sh

ENTRYPOINT [ "/root/entrypoint.sh" ]

CMD [ "caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
