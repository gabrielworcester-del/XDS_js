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
# Restart Bluetooth once immediately after the web listener starts.
server_pid=$$
(
  exec 9>&-
  deadline=$((SECONDS + 30))
  while ((SECONDS < deadline)); do
    kill -0 "$server_pid" 2>/dev/null || exit 0
    if ss -ltnH 'sport = :8080' | grep -q .; then
      kill -0 "$server_pid" 2>/dev/null || exit 0
      echo '[Movella] Restarting Bluetooth.'
      if systemctl restart bluetooth.service && systemctl is-active --quiet bluetooth.service; then
        echo '[Movella] Bluetooth restart complete. Confirm blePoweredOn: true before connecting.'
      else
        echo '[Movella] Bluetooth restart failed. Stop with Ctrl+C and inspect Bluetooth.' >&2
        exit 1
      fi
      exit 0
    fi
    sleep 0.1
  done
  echo '[Movella] Port 8080 did not become ready; Bluetooth was not restarted. Inspect the server or restart Bluetooth manually.' >&2
) &
echo '[Movella] Starting server. Wait for Bluetooth restart complete before connecting.'
exec node xsensDotServer.js
