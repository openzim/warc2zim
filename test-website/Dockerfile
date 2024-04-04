FROM caddy:2.6.1-alpine
LABEL org.opencontainers.image.source https://github.com/openzim/warc2zim

COPY Caddyfile /etc/caddy/Caddyfile

COPY content/ /var/www/html/

RUN apk add --no-cache bash

COPY entrypoint.sh /root/entrypoint.sh

ENTRYPOINT [ "/root/entrypoint.sh" ]

CMD [ "caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]

# # #---

# # # FROM dunglas/frankenphp:1.1.2-builder-php8.2.17-alpine AS builder

# # # # Copy xcaddy in the builder image
# # # COPY --from=caddy:2.7.6-builder-alpine /usr/bin/xcaddy /usr/bin/xcaddy

# # # # CGO must be enabled to build FrankenPHP
# # # ENV CGO_ENABLED=1 XCADDY_SETCAP=1 XCADDY_GO_BUILD_FLAGS="-ldflags '-w -s'"
# # # RUN xcaddy build \
# # # 	--output /usr/local/bin/frankenphp \
# # # 	--with github.com/dunglas/frankenphp=./ \
# # # 	--with github.com/dunglas/frankenphp/caddy=./caddy/
# # #     # Mercure and Vulcain are included in the official build, but feel free to remove them
# # # 	# --with github.com/dunglas/caddy-cbrotli \
# # # 	# --with github.com/dunglas/mercure/caddy \
# # # 	# --with github.com/dunglas/vulcain/caddy
# # # 	# Add extra Caddy modules here

# # FROM dunglas/frankenphp:1.1.2-php8.2.17 AS runner

# # # Replace the official binary by the one contained your custom modules
# # # COPY --from=builder /usr/local/bin/frankenphp /usr/local/bin/frankenphp

# # COPY content/ /app/public
