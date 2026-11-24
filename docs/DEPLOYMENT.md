# Raspberry Pi deployment — Patch 5.2.3

See the [README](../README.md) for installation and acquisition workflow.

## Dependencies

The baseline is Raspberry Pi OS Bookworm ARM64 with Node 18.x. Run `bash setup_dependencies.sh` as the desktop user. The script installs missing apt packages, verifies the Node major version, uses `npm ci`, and checks that native liblsl loads through Koffi. Node 18 is a historical compatibility baseline and is end-of-life; runtime migration is a separate task.

Existing liblsl is reused. If missing, install a trusted package compatible with your OS and architecture, or supply an independently verified package hash:

```bash
LIBLSL_SHA256="REPLACE_WITH_VERIFIED_SHA256" bash setup_dependencies.sh
```

Replace the placeholder with the actual 64-character hexadecimal digest before running. Optionally set `LIBLSL_URL` to the matching HTTPS package URL. The historical default asset URL has not been independently verified. No unchecked native download is installed. `LIBLSL_PATH` can specify an alternate installed library.

## Startup

```bash
bash install_launcher.sh
bash run_movella.sh network
# Alternatively, for Pi-local LSL:
# bash run_movella.sh local
# For a different HCI adapter:
# NOBLE_HCI_DEVICE_ID=1 bash run_movella.sh network
```

Desktop launch defaults to network mode. First launch runs setup if the lockfile stamp or node_modules is missing. The repair shortcut forces dependency repair. Administrative operations prompt in the terminal; no password is saved. The launcher uses the existing sudo-based acquisition arrangement; no passwordless sudo or service is installed.

Patch 5.2.3 checks for a free port and takes a lock before starting the server. A background helper checks for port 8080 at 100 ms intervals for up to 30 seconds and restarts Bluetooth once when the listener appears. It does not wait for Noble readiness before restarting and has no deliberate post-listener delay. Wait for the restart completion message and confirm `blePoweredOn: true` before scanning. A restart may disconnect other Bluetooth peripherals. If restart fails or the listener times out, stop the server with Ctrl+C and investigate; a background-helper failure does not automatically stop Node.

Use the normal launcher, not direct Node startup, to obtain this behavior. Stop with Ctrl+C and verify port release before restarting. Do not reset Bluetooth during active scanning, connections or acquisition. Charge DOTs and power-cycle them when recovering from failed sessions. The stale peripheral state explanation remains a hypothesis.

If migrating from older desktop launchers, remove the obsolete generated `.movella/bin/sudo` shim if present after stopping the server and reinstall the shortcuts.

## Acceptance checks

- Fresh clone dependency setup and repeated launch.
- Duplicate launch rejection and clean Ctrl+C shutdown; port release.
- Bluetooth restart completion and repeated multi-DOT connections.
- Successful synchronization, one Complete Euler LSL stream per expected DOT, plausible data, and functioning GUI/CSV logging.
- Local-mode discovery with the same LSLAPICFG on consumers; network-mode discovery from a second host.
- Experimental timing characterization, packet completeness and latency before relying on data for research.

Historical manual post-launch restart tests passed 3/3 three-DOT trials, versus 0/3 without restart. This is not a general reliability guarantee. No additional hardware or clean-install testing was performed as part of this documentation revision.
