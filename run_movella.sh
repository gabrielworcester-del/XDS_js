#!/usr/bin/env bash
# Run from anywhere: ./run_movella.sh local  or  ./run_movella.sh network
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-network}"

# Restart Bluetooth before Noble loads, never between scan and connect.
restart_bluetooth_before_server() {
    echo "[BLE] Restarting bluetooth.service before starting Noble..."
    sudo systemctl restart bluetooth
    if ! sudo systemctl is-active --quiet bluetooth; then
        echo "[BLE] Bluetooth service did not become active" >&2
        return 1
    fi

    # Wait for controller readiness; avoid a fixed sleep-only assumption.
    local attempt
    for attempt in {1..12}; do
        if timeout 3s bluetoothctl show 2>/dev/null | grep -q 'Powered: yes'; then
            echo "[BLE] Bluetooth adapter is ready"
            return 0
        fi
        sleep 0.5
    done
    echo "[BLE] Bluetooth adapter did not report Powered: yes" >&2
    return 1
}

case "$MODE" in
  local)
    CFG="$HERE/lsl_local.cfg"
    [[ -f "$CFG" ]] || { echo "Missing $CFG" >&2; exit 1; }
    echo "[MODE] Local LSL only (loopback 127.0.0.1; no external network required)"
    echo "[MODE] Local viewers must use: LSLAPICFG=$CFG"
    restart_bluetooth_before_server
    exec sudo env "LSLAPICFG=$CFG" "NOBLE_HCI_DEVICE_ID=${NOBLE_HCI_DEVICE_ID:-0}" node "$HERE/xsensDotServer.js"
    ;;
  network)
    echo "[MODE] Network LSL (existing/default liblsl configuration)"
    # Prevent an inherited config from silently enabling local mode.
    restart_bluetooth_before_server
    exec sudo env -u LSLAPICFG "NOBLE_HCI_DEVICE_ID=${NOBLE_HCI_DEVICE_ID:-0}" node "$HERE/xsensDotServer.js"
    ;;
  *)
    echo "Usage: $0 {local|network}" >&2; exit 2 ;;
esac
