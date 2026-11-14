FROM docker.io/zmkfirmware/zmk-build-arm@sha256:edb1c953438c6f720ddb79c3762f3972013b7fbbaf4fff3592fc869983e7afc5

RUN --mount=type=bind,target=/build-source,ro --mount=type=secret,id=ca_bundle \
    set -eu; \
    mkdir -p /app/config; \
    cp /build-source/config/west.yml /app/config/west.yml; \
    cp /build-source/bin/build.sh /app/build.sh; \
    cp /build-source/scripts/update_west.py /app/update_west.py; \
    if [ -f /run/secrets/ca_bundle ]; then export GIT_SSL_CAINFO=/run/secrets/ca_bundle; fi; \
    cd /app; \
    west init -l config; \
    python3 /app/update_west.py --update-workspace /app; \
    west zephyr-export

WORKDIR /app

CMD ["./build.sh"]
