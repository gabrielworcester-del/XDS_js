# Raspberry Pi deployment (Patch 5.1)

On Raspberry Pi OS Bookworm ARM64, run `bash install_launcher.sh` once from the repository as the desktop user. Double-click **Launch Movella DOT** for normal operation, or **Install / Repair Movella DOT** for explicit dependency repair. First launch automatically runs setup if the lockfile stamp or node_modules is absent. Administrative operations prompt in the terminal; no password is saved. Open the existing web GUI at http://localhost:8080 (or the Pi IP on a remote computer). Stop using Ctrl+C, then verify the port is free before another run. Bluetooth restarts once per launch, disrupting other Bluetooth connections.

CLI equivalents: `bash run_movella.sh network`, `bash run_movella.sh local`, `NOBLE_HCI_DEVICE_ID=1 bash run_movella.sh network`. Desktop launch defaults to network mode and adapter 0 unless the desktop environment specifies another adapter. `LIBLSL_PATH` is preserved. Existing native liblsl is reused. If missing, install a trusted matching package manually or run `LIBLSL_SHA256=<independently verified SHA256> bash setup_dependencies.sh` with an optional `LIBLSL_URL` override. The historical default asset URL is not independently verified. No unchecked native download is installed. Node 18 is the historical project baseline, not a supported long-term security baseline; migrate separately.

Do not run npm as root. The server uses the existing sudo-based acquisition arrangement; do not run untrusted repository code. No passwordless sudo or new service is installed.

After stopping the old GUI and server, remove the obsolete generated shim `.movella/bin/sudo` if present; keep logs until no longer needed. Reinstall desktop entries to replace the previous GUI shortcut. Git tracks source history; do not keep patch archives or backup copies inside the repository.

Hardware acceptance: verify dependency setup, repeated launch, duplicate launch rejection, configured adapter readiness, Ctrl+C and port release, local/network LSL discovery, and multi-DOT synchronization. No physical testing was performed for this patch.
