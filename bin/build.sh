#!/usr/bin/env bash

set -euo pipefail

PWD=$(pwd)
TIMESTAMP="${TIMESTAMP:-$(date -u +"%Y%m%d%H%M")}"
COMMIT="${COMMIT:-$(echo xxxxxx)}"
ZEPHYR_BUILD_VERSION=$(git -C zephyr rev-parse HEAD | cut -c1-12)

# West Build (left)
west build -s zmk/app -p -d build/left -b adv360_left -S studio-rpc-usb-uart -- -DZMK_CONFIG="${PWD}/config" -DCONFIG_ZMK_STUDIO=y -DBUILD_VERSION="${ZEPHYR_BUILD_VERSION}"
# Adv360 Left Kconfig file
grep -vE '(^#|^$)' build/left/zephyr/.config
# Rename zmk.uf2
cp build/left/zephyr/zmk.uf2 "./firmware/${TIMESTAMP}-${COMMIT}-left-clique.uf2"

# Build right side if selected
if [ "${BUILD_RIGHT}" = true ]; then
    # West Build (right)
    west build -s zmk/app -p -d build/right -b adv360_right -- -DZMK_CONFIG="${PWD}/config" -DBUILD_VERSION="${ZEPHYR_BUILD_VERSION}"
    # Adv360 Right Kconfig file
    grep -vE '(^#|^$)' build/right/zephyr/.config
    # Rename zmk.uf2
    cp build/right/zephyr/zmk.uf2 "./firmware/${TIMESTAMP}-${COMMIT}-right-clique.uf2"
fi

cp config/west.yml firmware/west-manifest.yml
west manifest --freeze --active-only > firmware/west-active-manifest.yml
printf 'source_revision=%s\nsource_dirty=%s\nsource_label=%s\nsource_date_epoch=%s\nimage=%s\nzephyr_build_version=%s\n' \
    "${BUILD_SOURCE_REVISION}" "${BUILD_SOURCE_DIRTY}" "${BUILD_SOURCE_LABEL}" "${SOURCE_DATE_EPOCH}" "${BUILD_IMAGE_REF}" "${ZEPHYR_BUILD_VERSION}" \
    > firmware/build-info.txt
find config -type f -print0 | sort -z | xargs -0 sha256sum > firmware/config-SHA256SUMS
(cd firmware && sha256sum -- *.uf2 > SHA256SUMS)
