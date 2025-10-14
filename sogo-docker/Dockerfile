FROM debian:bookworm-slim

LABEL maintainer="Edulution <support@edulution.io>"
LABEL description="Custom SOGo container with SQL group expansion support"

ARG DEBIAN_FRONTEND=noninteractive
ARG DEBIAN_VERSION=bookworm
ARG SOGO_DEBIAN_REPOSITORY=https://packagingv2.sogo.nu/sogo-nightly-debian/
# renovate: datasource=github-releases depName=tianon/gosu versioning=semver-coerced extractVersion=^(?<version>.*)$
ARG GOSU_VERSION=1.17
ENV LC_ALL=C

# Prerequisites
RUN echo "Building from repository $SOGO_DEBIAN_REPOSITORY" \
  && apt-get update && apt-get install -y --no-install-recommends \
  apt-transport-https \
  ca-certificates \
  gettext \
  gnupg \
  mariadb-client \
  rsync \
  supervisor \
  syslog-ng \
  syslog-ng-core \
  syslog-ng-mod-redis \
  dirmngr \
  netcat-traditional \
  psmisc \
  wget \
  patch \
  php-fpm \
  php-mysql \
  php-pdo \
  nginx \
  && dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')" \
  && wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch" \
  && chmod +x /usr/local/bin/gosu \
  && gosu nobody true \
  && mkdir /usr/share/doc/sogo \
  && touch /usr/share/doc/sogo/empty.sh \
  && wget -O- https://keys.openpgp.org/vks/v1/by-fingerprint/74FFC6D72B925A34B5D356BDF8A27B36A6E2EAE9 | gpg --dearmor | apt-key add - \
  && echo "deb [trusted=yes] ${SOGO_DEBIAN_REPOSITORY} ${DEBIAN_VERSION} main" > /etc/apt/sources.list.d/sogo.list \
  && apt-get update && apt-get install -y --no-install-recommends \
    sogo \
    sogo-activesync \
  && apt-get autoclean \
  && rm -rf /var/lib/apt/lists/* \
  && touch /etc/default/locale

COPY ./bootstrap-sogo.sh /bootstrap-sogo.sh
COPY syslog-ng.conf /etc/syslog-ng/syslog-ng.conf
COPY syslog-ng-redis_slave.conf /etc/syslog-ng/syslog-ng-redis_slave.conf
COPY supervisord.conf /etc/supervisor/supervisord.conf
COPY acl.diff /acl.diff
COPY navMailcowBtns.diff /navMailcowBtns.diff
COPY card-sql-groups.patch /card-sql-groups.patch
COPY plist_ldap_groups.sh /plist_ldap_groups.sh
COPY stop-supervisor.sh /usr/local/sbin/stop-supervisor.sh
COPY inject-js.sh /inject-js.sh
COPY docker-entrypoint.sh /

# Edulution: Add SQL group expansion middleware
COPY group-resolver.php /usr/lib/GNUstep/SOGo/WebServerResources/group-resolver.php
COPY sql-groups.js /usr/lib/GNUstep/SOGo/WebServerResources/js/sql-groups.js
COPY nginx-group-resolver.conf /etc/nginx/sites-available/group-resolver
RUN ln -s /etc/nginx/sites-available/group-resolver /etc/nginx/sites-enabled/group-resolver \
  && rm -f /etc/nginx/sites-enabled/default

RUN chmod +x /bootstrap-sogo.sh \
  /usr/local/sbin/stop-supervisor.sh \
  /inject-js.sh \
  /plist_ldap_groups.sh \
  && chmod 644 /usr/lib/GNUstep/SOGo/WebServerResources/group-resolver.php \
  && chmod 644 /usr/lib/GNUstep/SOGo/WebServerResources/js/sql-groups.js

ENTRYPOINT ["/docker-entrypoint.sh"]

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]