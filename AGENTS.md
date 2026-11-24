# Codex Project Instructions â€” XDS_js (Movella DOT â†’ LSL)

> Repository: `gabrielworcester-del/XDS_js`  
> Context snapshot: 2026-11-16. **The checked-out code is the source of truth.** Reinspect files, `git status`, and recent changes before relying on this document; it is not a substitute for the current implementation.

## Project purpose

This repository is a modified version of the archived Xsens DOT Server. Its purpose is to acquire real-time data from Movella/Xsens DOT inertial sensors through Bluetooth Low Energy (BLE) on a Raspberry Pi and make that data usable through the existing web GUI/CSV workflow and Lab Streaming Layer (LSL).

The larger research goals are reliable multi-DOT acquisition, traceable timestamps, robust synchronization, and low-latency data streams for scientific recording and analysis. **Do not represent proposed features as implemented.** Hardware validation is necessary for claims about connection reliability, latency, synchronization, or timing accuracy.

## Working environment

- Primary runtime: Raspberry Pi, Debian 12 (bookworm), aarch64, with Bluetooth/BlueZ.
- Known working development setup: Node.js 18.x and npm 10.x on the Pi. Check installed versions before changing dependencies.
- BLE backend: `@abandonware/noble` (replacing the unsupported original Noble dependency). The native HCI socket package is part of the Pi installation.
- Server/UI: Node.js, Express, Socket.IO, browser GUI on **port 8080**.
- LSL: Node.js `koffi` FFI calling the native **`liblsl.so`** C API. `koffi` and native liblsl must be installed/available on the runtime; check actual installation rather than assuming `package.json` provisions them. `LIBLSL_PATH` can override the library path.
- Python is useful for diagnostics with `pylsl`, but Python does **not** implement the main sensor server.
- The current `README.md` and `docs/DEPLOYMENT.md` describe the Raspberry Pi workflow; historical upstream PDFs are retained for reference.

## Current architecture â€” verify against source before edits

```text
Movella DOT BLE notifications
          |
          v
bleHandler.js  (@abandonware/noble; decode + timestamp)
          |                          \
          v                           \ (Complete Euler measurement)
sensorServer.js                        v
(state machine, GUI, CSV)         lslPublisher.js
          |                       (koffi -> native liblsl)
          v                            |
webGuiHandler.js + communication.js     v
(browser control, port 8080)         LSL stream per DOT
                                       |
                               local Pi or network consumers
```

**Important:** In the checked repository, data is passed **directly from `bleHandler.js` to `lslPublisher.js`**. There is **no UDP relay between those two modules** in the current implementation. Do not invent or silently introduce one in descriptions or code.

### File responsibilities

| File | Role |
| --- | --- |
| `xsensDotServer.js` | Original, intentionally minimal server entry point. Preserve unless there is a demonstrated need to change it. |
| `bleHandler.js` | Noble BLE scan/connect/disconnect, characteristic discovery, measurement notifications, payload decoding, timestamp handling, and call into `lslPublisher`. Also forwards data into the original application pathway. |
| `sensorServer.js` | Event-driven sensor/application state machine; routes BLE events, GUI actions, and existing CSV recording. |
| `syncManager.js` | DOT sensor synchronization workflow, root sensor selection, success/failure handling, and synchronization state passed to LSL. |
| `lslPublisher.js` | Direct liblsl publisher, sensor-specific outlets, stream metadata, and acquisition-time-to-LSL-time conversion. |
| `lsl_local.cfg` | Explicit loopback-only LSL discovery/network configuration for Pi-local viewing. |
| `run_movella.sh` | Pi startup helper with `local` and `network` modes; restarts Bluetooth once immediately after the web listener starts (before scanning or connecting). |
| `check_local_lsl.py` | `pylsl` diagnostic that discovers `Xsens_DOT_` streams and reads one sample. |
| `webGuiHandler.js` | Express/Socket.IO web-server interface. |
| `communication.js` | Browser-side GUI communication and sensor/event interactions. |
| `functionalComponent.js` | Reusable finite-state-machine framework. |
| `global.js` | Shared global state and measurement-payload constants. |
| `styleSheet.css` / `index.html` | Browser UI styling and markup. |
| `package.json` / `package-lock.json` | Declared Node dependencies and lockfile. Treat changes to native dependencies cautiously. |

`*.bak*` files and `patch_movella_*.py` / `movella_lsl_fix.py` files are historical backups/patch utilities, **not authoritative runtime modules**. Avoid editing or rerunning them unless specifically asked.

## Existing LSL behavior and data contract

- `lslPublisher.js` creates up to **five** DOT outlets, named `Xsens_DOT_<sanitized_sensor_address>`, with LSL type `IMU`.
- LSL publication currently targets **Complete Euler (measurement payload ID 16)**, not every payload type supported by the legacy GUI.
- Each outlet contains **7 double-precision channels**, in this order:
  1. `sensor_time_us`
  2. `euler_x` (degrees)
  3. `euler_y` (degrees)
  4. `euler_z` (degrees)
  5. `freeAcc_x` (m/sÂ²)
  6. `freeAcc_y` (m/sÂ²)
  7. `freeAcc_z` (m/sÂ²)
- The stream nominal sampling rate is **0 (irregular)**. Do not change it to a guessed fixed rate. Consumers should handle timestamps rather than assuming perfectly periodic delivery.
- In synchronized operation, LSL publishing begins only after the expected DOT group successfully synchronizes; the publisher uses a shared root-synchronized sensor-time anchor and handles 32-bit microsecond timestamp rollover. A failed/incomplete group must not be advertised as synchronized.
- In unsynchronized operation, the source currently supports **one** DOT with an LSL timestamp taken at BLE packet arrival. It **must not** be described as multi-sensor synchronized data.
- `sensor_time_us` is not inherently an absolute UTC timestamp. The derived LSL timestamp is not proof of zero-latency delivery: the initial anchor contains BLE-arrival delay. Clearly distinguish sensor/sample time, Pi host arrival time, LSL clock time, and wall-clock/UTC time in analysis.
- LSL/native failures should not bring down the original BLE/GUI/CSV server; preserve the existing protective error handling.
- Maintain the original GUI/CSV data pathway when making LSL-specific changes.

## Known issues / work in progress

These are observed issues or investigation targets, **not claims that the newest code has resolved them**:

- A single DOT has successfully been discovered and streamed over LSL; multi-DOT connection, synchronized acquisition, and reliable simultaneous publication require further hardware verification.
- Subsequent sensor connections have sometimes stalled in Noble's `connecting` state, including missing callbacks / HCI connection events. Scanning and connection ordering may matter.
- State-machine issues have included unexpected `startScanning` while BLE is powering on and unexpected `blePoweredOn` while the sensor server is idle. Avoid issuing events in inappropriate states.
- Synchronization has sometimes succeeded for several DOTs while fewer DOTs actually produced usable measurement streams.
- Desired future diagnostics include per-sensor sampling-interval jitter, inter-sensor time offset, host arrival delay, packet drops, and CSV exports. **Inspect code before stating any of these metrics are already recorded**; existing CSV recording alone is not a validated latency measurement.
- Local loopback-only LSL discovery is distinct from publishing onto the local wireless network. Network discovery, firewall rules, and host configuration must be tested independently.

## Run and diagnose on the Raspberry Pi

From the repository root (`~/XDS_js` on the known Pi):

```bash
# Recommended startup: choose one mode
./run_movella.sh local
./run_movella.sh network

# Alternate direct startup (network/default LSL configuration)
sudo env NOBLE_HCI_DEVICE_ID=0 node xsensDotServer.js

# Verify a local-only LSL stream from another Pi terminal
cd ~/XDS_js
export LSLAPICFG="$PWD/lsl_local.cfg"
python3 check_local_lsl.py

# Manual BLE reset only when no scan, connection attempt or recording is active
sudo systemctl restart bluetooth
```

For the local mode, viewers must also load the same `lsl_local.cfg` through `LSLAPICFG`. In either mode, connect and enable a DOT through the GUI before expecting live samples. Access the browser UI via `http://<PI_IP>:8080/` or `http://localhost:8080/` on the Pi. Do not assume any historical lab IP address remains valid.

**Do not restart Bluetooth in the middle of a live Noble scan/connect/recording attempt.** The startup script performs the reset once after the port 8080 listener appears; wait for restart completion before scanning.

## Coding and debugging instructions for Codex

1. **Inspect first.** Read the relevant implementation, `git status`, and surrounding state transitions before proposing edits. Treat this document as context, not runtime evidence.
2. **Prefer minimal, reviewable patches.** Preserve existing naming conventions, behavior, comments, GUI controls, and CSV compatibility. Avoid wholesale rewrites of the archived server.
3. **Respect the state machine.** For BLE bugs, trace scan requests, `poweredOn` notifications, active connections, pending callbacks, disconnects, and synchronization events across `bleHandler.js`, `sensorServer.js`, and `syncManager.js`.
4. **Protect sensor/data integrity.** Do not fabricate samples or timestamps, conceal packet loss, silently resample data, or claim synchronization without the requisite acknowledgment. Keep units and clock domains explicit.
5. **Separate hypotheses from observations.** Identify suspected root causes and what logs or experiments would confirm them. Distinguish code inspection, simulated tests, and actual Pi/DOT hardware results.
6. **Preserve runtime resilience.** Fail gracefully when native liblsl is unavailable. Avoid blocking the BLE notification handler with heavy computation, logging, or unnecessary network writes.
7. **Preserve LSL mode isolation.** Do not make local mode discoverable off-device or change network behavior without a deliberate request. Never hardcode IP addresses, sensor MACs, or BLE adapter identity.
8. **Avoid unintended destructive actions.** No automatic `git reset --hard`, mass file deletion, history rewriting, forced `git pull`, firmware updates, system package upgrades, or Bluetooth/network reconfiguration. Ask before invasive changes. Preserve local modifications to `run_movella.sh` and other tracked files.
9. **For dependency changes**, distinguish npm dependencies from OS/native libraries. Explain compatibility risks on Linux aarch64 and keep `package.json` and the lockfile consistent if either changes.
10. **When replying**, provide: (a) root-cause hypothesis/goal, (b) exact files changed, (c) why, (d) tests run with actual results, (e) hardware checks still required. Be concise and technical.

## Validation checklist

Run relevant checks after editing, when the required tools are installed:

```bash
node --check bleHandler.js
node --check sensorServer.js
node --check syncManager.js
node --check lslPublisher.js
node --check xsensDotServer.js
bash -n run_movella.sh
python3 -m py_compile check_local_lsl.py
```

Then inspect the patch with `git diff --check` and `git diff`. Do **not** call syntax checks hardware validation. A full real-world check, when the user can run it on a Pi with DOTs, is: scan â†’ connect â†’ enable Complete Euler â†’ synchronize (if multiple sensors) â†’ inspect `Xsens_DOT_` outlet(s) â†’ receive plausible channel data â†’ stop/disconnect cleanly â†’ confirm GUI/CSV still works. Exercise both `local` and `network` configurations as relevant.

## Priority for future improvements

1. Robust and repeatable connections for two or more DOTs without hanging BLE operations.
2. Reliable synchronization and correct per-sensor LSL publication after group synchronization.
3. Timestamp transparency and objective jitter/offset/packet-loss diagnostics.
4. Reproducible performance tests and clear documentation for other researchers.

When asked to implement one of these, propose the smallest measurable change and its acceptance test before making broad architectural modifications.

## Source and attribution

This code descends from the archived Xsens DOT Server and retains its original copyright/license notices. Preserve existing attribution and applicable license conditions. The current fork's source files take precedence over historical documentation or notes about earlier prototypes.
