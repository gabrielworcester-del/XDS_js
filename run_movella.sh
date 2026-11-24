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
# Observe the real server's startup output without changing acquisition code.
# The foreground Node process keeps its normal terminal signal handling.
startup_log=$(mktemp /tmp/movella-startup.XXXXXXXX)
server_pid=$$
(
  exec 9>&-
  trap 'rm -f -- "$startup_log"' EXIT
  deadline=$((SECONDS + 30))
  while ((SECONDS < deadline)); do
    kill -0 "$server_pid" 2>/dev/null || exit 0
    if grep -q 'Webserver listening on port 8080' "$startup_log" &&
       grep -q 'blePoweredOn: true' "$startup_log"; then
      echo '[Movella] Server ready; restarting Bluetooth before sensor connections.'
      if ! systemctl restart bluetooth.service || ! systemctl is-active --quiet bluetooth.service; then
        echo '[Movella] Bluetooth restart failed. Stop the server with Ctrl+C and investigate.' >&2
        exit 1
      fi
      sleep 3
      kill -0 "$server_pid" 2>/dev/null || exit 0
      echo '[Movella] Bluetooth restart complete. You may now scan and connect fully charged DOTs.'
      exit 0
    fi
    sleep 0.2
  done
  echo '[Movella] Startup readiness timeout. Do not connect; stop with Ctrl+C and inspect the logs.' >&2
  exit 1
) &
echo '[Movella] Starting server. Wait for Bluetooth restart complete before connecting.'
exec node xsensDotServer.js > >(exec 9>&-; exec 8>>"$startup_log"; awk -v markerfile=/dev/fd/8 '{ print; fflush(); if (!web && /Webserver listening on port 8080/) { print "Webserver listening on port 8080" >> markerfile; close(markerfile); web=1 } if (!ble && /blePoweredOn: true/) { print "blePoweredOn: true" >> markerfile; close(markerfile); ble=1 } }' ) 2>&1
