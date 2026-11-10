#!/usr/bin/env bash
# Run from anywhere: ./run_movella.sh local  or  ./run_movella.sh network
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-network}"
case "$MODE" in
  local)
    CFG="$HERE/lsl_local.cfg"
    [[ -f "$CFG" ]] || { echo "Missing $CFG" >&2; exit 1; }
    echo "[MODE] Local LSL only (loopback 127.0.0.1; no external network required)"
    echo "[MODE] Local viewers must use: LSLAPICFG=$CFG"
    exec sudo env "LSLAPICFG=$CFG" "NOBLE_HCI_DEVICE_ID=${NOBLE_HCI_DEVICE_ID:-0}" node "$HERE/xsensDotServer.js"
    ;;
  network)
    echo "[MODE] Network LSL (existing/default liblsl configuration)"
    # Prevent an inherited config from silently enabling local mode.
    exec sudo env -u LSLAPICFG "NOBLE_HCI_DEVICE_ID=${NOBLE_HCI_DEVICE_ID:-0}" node "$HERE/xsensDotServer.js"
    ;;
  *)
    echo "Usage: $0 {local|network}" >&2; exit 2 ;;
esac
