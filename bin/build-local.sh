#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
case "${1:-all}" in
all) build_right=true ;;
left) build_right=false ;;
*) echo 'usage: build-local.sh [all|left]' >&2; exit 2 ;;
esac
engine=${DOCKER:-$(command -v podman || command -v docker)}
revision=$(git -C "${root}" rev-parse HEAD)
source_dirty=false
[[ -z $(git -C "${root}" status --porcelain) ]] || source_dirty=true
commit=${revision:0:7}
branch=${BUILD_SOURCE_LABEL:-$(git -C "${root}" rev-parse --abbrev-ref HEAD | cut -c1-4)}
epoch=${SOURCE_DATE_EPOCH:-$(date -u +%s)}
[[ "${epoch}" =~ ^[0-9]+$ ]] || { echo 'SOURCE_DATE_EPOCH must be a nonnegative Unix timestamp' >&2; exit 2; }
if [[ $(uname) == Darwin ]]; then
	timestamp=$(date -u -r "${epoch}" +%Y%m%d%H%M)
else
	timestamp=$(date -u -d "@${epoch}" +%Y%m%d%H%M)
fi
scratch=$(mktemp -d)
trap 'rm -rf "${scratch}"' EXIT
mkdir -p "${scratch}/config" "${scratch}/firmware"
cp -R "${root}/config/." "${scratch}/config/"
(
	cd "${scratch}"
	bash "${root}/bin/get_version.sh" "${branch}" "${commit}" clique "${timestamp:0:8}"
)
build_options=()
if [[ -n "${SSL_CERT_FILE:-}" ]]; then
	[[ -r "${SSL_CERT_FILE}" ]] || { echo 'Configured TLS trust bundle is unreadable' >&2; exit 1; }
	build_options+=(--secret "id=ca_bundle,src=${SSL_CERT_FILE}")
fi
"${engine}" build "${build_options[@]}" --iidfile "${scratch}/image-id" --tag adv360-zmk --file "${root}/Dockerfile" "${root}"
image_id=$(cat "${scratch}/image-id")
label=
[[ $(uname) == Darwin ]] || label=,z
"${engine}" run --rm --network none \
	-v "${scratch}/firmware:/app/firmware:rw${label}" \
	-v "${scratch}/config:/app/config:ro${label}" \
	-e "TIMESTAMP=${timestamp}" -e "COMMIT=${commit}" -e "BUILD_RIGHT=${build_right}" \
	-e "SOURCE_DATE_EPOCH=${epoch}" -e "BUILD_SOURCE_REVISION=${revision}" \
	-e "BUILD_SOURCE_DIRTY=${source_dirty}" \
	-e "BUILD_SOURCE_LABEL=${branch}" \
	-e "BUILD_IMAGE_REF=$(sed -n 's/^FROM //p' "${root}/Dockerfile")" \
	"${image_id}"
mkdir -p "${root}/firmware"
cp "${scratch}/firmware/"* "${root}/firmware/"
