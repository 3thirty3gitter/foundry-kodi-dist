# QA only: official Debian 13 amd64 Kodi 21.2 / Python 3.13.
# Base and every installed package match the validated concurrent-script runtime.
FROM debian@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp/foundry-home XDG_CONFIG_HOME=/tmp/foundry-config XDG_CACHE_HOME=/tmp/foundry-cache
COPY packages.lock /qa-packages.lock
RUN apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o APT::Update::Error-Mode=any update \
    && awk '{print $1 "=" $2}' /qa-packages.lock | xargs apt-get install -y --no-install-recommends \
    && dpkg-query -W > /qa-package-versions.txt \
    && diff -u /qa-packages.lock /qa-package-versions.txt \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work/foundry-kodi-dist
