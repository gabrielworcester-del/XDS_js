#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(realpath -- "$0")")"
mode=${1:-network}
case "$mode" in
  local) [[ -f lsl_local.cfg ]] || { echo 'Missing lsl_local.cfg'; exit 1; }; export LSLAPICFG="$PWD/lsl_local.cfg";;
  network) unset LSLAPICFG;;
  *) echo 'Usage: run_movella.sh local|network'; exit 2;;
esac
export NOBLE_HCI_DEVICE_ID="${NOBLE_HCI_DEVICE_ID:-0}"
[[ $NOBLE_HCI_DEVICE_ID =~ ^[0-9]+$ ]] || { echo 'Invalid HCI adapter index'; exit 2; }
if [[ $EUID != 0 ]]; then
  if ! [[ -d node_modules ]] || ! sha256sum -c --status .movella/dependencies.sha256 2>/dev/null; then
    echo 'Dependencies missing or changed. Running setup first.'
    bash setup_dependencies.sh
  fi
  envargs=("NOBLE_HCI_DEVICE_ID=$NOBLE_HCI_DEVICE_ID")
  [[ -z ${LIBLSL_PATH:-} ]] || envargs+=("LIBLSL_PATH=$LIBLSL_PATH")
  exec sudo env -u LSLAPICFG "${envargs[@]}" bash "$PWD/run_movella.sh" "$mode"
fi
exec 9>/run/lock/movella-dot.lock
flock -n 9 || { echo 'Movella server already running'; exit 1; }
if ss -ltnH 'sport = :8080' | grep -q .; then echo 'Port 8080 already in use'; exit 1; fi
node -e 'require("koffi").load(process.env.LIBLSL_PATH || "liblsl.so")'
echo '[Movella] Restarting Bluetooth (other Bluetooth connections may disconnect).'
systemctl restart bluetooth.service
systemctl is-active --quiet bluetooth.service
adapter="hci$NOBLE_HCI_DEVICE_ID"
ready=false
for ((i=0;i<20;i++)); do
  if [[ -r /sys/class/bluetooth/$adapter/address ]]; then
    address=$(cat "/sys/class/bluetooth/$adapter/address")
    if bluetoothctl show "$address" | grep -q 'Powered: yes'; then ready=true; break; fi
    timeout 3 btmgmt --index "$NOBLE_HCI_DEVICE_ID" power on >/dev/null 2>&1 || true
  fi
  sleep 1
done
[[ $ready == true ]] || { echo "Bluetooth adapter $adapter not ready"; exit 1; }
echo "[Movella] Starting $mode LSL on $adapter. Press Ctrl+C to stop."
exec node xsensDotServer.js
