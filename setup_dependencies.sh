#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(realpath -- "$0")")"
[[ $EUID != 0 ]] || { echo 'Run as the desktop user, not root'; exit 1; }
[[ -f package-lock.json && -f package.json ]] || { echo 'Missing npm manifest or lockfile'; exit 1; }
packages=(nodejs npm bluez libbluetooth-dev libusb-1.0-0-dev build-essential python3 curl ca-certificates iproute2 util-linux)
missing=(); for p in "${packages[@]}"; do dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed' || missing+=("$p"); done
if ((${#missing[@]})); then sudo apt-get update; sudo apt-get install -y "${missing[@]}"; fi
[[ $(node -p 'process.versions.node.split(".")[0]') == 18 ]] || { echo 'Expected Node 18 for this historical baseline; runtime migration is separate.'; exit 1; }
if [[ ${1:-} == --repair || ! -d node_modules ]] || ! sha256sum -c --status .movella/dependencies.sha256 2>/dev/null || ! node -e 'require("koffi"); require("@abandonware/noble")' >/dev/null 2>&1; then
  npm ci
fi
if ! node -e 'require("koffi").load(process.env.LIBLSL_PATH || "liblsl.so")'; then
  . /etc/os-release
  [[ ${VERSION_CODENAME:-} == bookworm && $(dpkg --print-architecture) == arm64 ]] || { echo 'Install matching native liblsl for your OS/architecture.'; exit 1; }
  url=${LIBLSL_URL:-https://github.com/sccn/liblsl/releases/download/v1.16.2/liblsl-1.16.2-bookworm_arm64.deb}
  hash=${LIBLSL_SHA256:-}
  if [[ ! $hash =~ ^[[:xdigit:]]{64}$ ]]; then
    echo 'Native liblsl missing. Install a trusted package manually, or supply LIBLSL_SHA256 (verified independently) and optionally LIBLSL_URL. No unverified package will be downloaded or installed.'
    exit 1
  fi
  tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
  curl --fail --location --retry 2 --proto '=https' --proto-redir '=https' "$url" -o "$tmp/liblsl.deb"
  printf '%s  %s\n' "$hash" "$tmp/liblsl.deb" | sha256sum --check --strict
  sudo apt-get install -y "$tmp/liblsl.deb"
  sudo ldconfig
  node -e 'require("koffi").load(process.env.LIBLSL_PATH || "liblsl.so")'
fi
mkdir -p .movella
sha256sum package.json package-lock.json > .movella/dependencies.sha256
echo 'Dependencies ready.'
