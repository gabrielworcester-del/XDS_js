# Movella DOT to Lab Streaming Layer (XDS_js)

A research-oriented modification of the original [Xsens DOT Server](https://github.com/xsens/xsens_dot_server) for real-time inertial data acquisition on Raspberry Pi and direct publication to [Lab Streaming Layer (LSL)](https://labstreaminglayer.org/).

**Current branch: `main`.** Deployment baseline: Patch 5.2.3. Use this branch when cloning or forking. This fork is independent of the archived upstream server and is not an official Movella product.

## Features

- Browser-based Bluetooth Low Energy (BLE) discovery, connection, measurement control, synchronization and CSV logging inherited from the original server.
- Direct LSL publication of Complete Euler measurements via the native liblsl C API, without an intermediate UDP relay or CSV polling.
- One LSL outlet per synchronized DOT, with a software limit of five outlets; one unsynchronized DOT is also supported.
- Local-only or network LSL modes, dependency setup and optional Raspberry Pi desktop launchers.
- A single Bluetooth service restart immediately after the web listener starts, before sensor connections.

## System architecture

```text
Movella / Xsens DOT sensors
          | BLE
          v
 Raspberry Pi: bleHandler.js
          |                  |
          v                  v
 sensorServer.js        lslPublisher.js
          |                  | Koffi / liblsl
          v                  v
 Web GUI / CSV          LSL consumers
 (TCP port 8080)        (local or network)
```

## Requirements

- Raspberry Pi OS Bookworm (64-bit ARM), a working Bluetooth adapter and charged DOT sensors.
- Node.js 18.x, npm, BlueZ and the native liblsl library. Node 18 is the historical compatibility baseline, not a currently maintained security baseline.
- A browser on the Pi or another computer on the same trusted network. Remote browser clients do not need Node.js or a Bluetooth adapter for this workflow.
- Optional: LabRecorder for XDF recording or an LSL-compatible viewer; Python with pylsl for diagnostics.

The supported deployment workflow targets Raspberry Pi Linux. Native Windows/macOS server installation is not validated for this fork.

## Installation

On the Pi, as your normal desktop user:

```bash
sudo apt-get update
sudo apt-get install -y git python3
cd ~
git clone https://github.com/gabrielworcester-del/XDS_js.git
cd XDS_js
bash setup_dependencies.sh
```

The setup script installs missing OS dependencies and uses `npm ci` with the committed lockfile. If native liblsl is missing, install a trusted compatible package or supply an independently verified SHA-256 checksum and, if needed, a package URL as described in [deployment instructions](docs/DEPLOYMENT.md). Do not use sudo to run npm or the setup script itself.

For optional desktop shortcuts:

```bash
bash install_launcher.sh
```

This creates **Launch Movella DOT** and **Install / Repair Movella DOT** entries. Mark the desktop files trusted if your file manager requires it.

## Quick start

Start network mode (or use the desktop launcher):

```bash
bash run_movella.sh network
```

1. Wait for `Bluetooth restart complete` and confirm `blePoweredOn: true` before scanning.
2. Open `http://localhost:8080/` on the Pi or `http://<PI_IP>:8080/` on a remote computer. Use `hostname -I` on the Pi to identify its network address.
3. Scan for DOTs, connect the required sensors, and select **Complete (Euler)** measurement mode. For multiple DOTs, complete the hardware synchronization workflow before expecting synchronized LSL outlets.
4. Start measurement and confirm the expected `Xsens_DOT_...` streams in your LSL consumer. Start LabRecorder recording if desired.
5. Stop measurement and recording, disconnect sensors, and stop the server with Ctrl+C.

For loopback-only LSL publication:

```bash
bash run_movella.sh local
```

Local-mode consumers must use the same `lsl_local.cfg` via `LSLAPICFG`. From a second Pi terminal with pylsl installed:

```bash
cd ~/XDS_js
export LSLAPICFG="$PWD/lsl_local.cfg"
python3 check_local_lsl.py
```

Local mode restricts LSL discovery, not access to the web GUI. Use only trusted networks; do not expose the server directly to the public internet.

## LSL data format

Stream name: `Xsens_DOT_<sanitized_sensor_address>`. Type: `IMU`. Payload: Complete Euler (ID 16). Seven double-precision channels, with nominal rate 0 (irregular):

| Index (1-based) | Channel | Unit |
| --- | --- | --- |
| 1 | sensor_time_us | microseconds (see timing caveat below) |
| 2 | euler_x | degrees |
| 3 | euler_y | degrees |
| 4 | euler_z | degrees |
| 5 | freeAcc_x | m/s² |
| 6 | freeAcc_y | m/s² |
| 7 | freeAcc_z | m/s² |

### Synchronization and timing

For a successfully synchronized group, the publisher maps root-synchronized 32-bit sensor timestamps to a shared LSL timebase, handling timestamp rollover. The anchor is established at first packet arrival and therefore includes initial BLE transport delay. For a single unsynchronized DOT, the first channel is a host-derived timestamp and the LSL sample timestamp uses BLE arrival time; do not interpret this as a synchronized hardware clock or assume the channel label establishes its units independently of the acquisition pathway.

LSL timestamps are not UTC timestamps. The implementation does not establish absolute sensor-to-host latency or guarantee a particular synchronization accuracy, packet-loss rate or maximum sustainable throughput. Validate timing and stream completeness for your experiment.

## Troubleshooting

- **Cannot connect:** Wait for the startup Bluetooth restart to finish; charge sensors, and power-cycle them after failed or abruptly terminated sessions if necessary. The restart can disconnect other Bluetooth peripherals.
- **No LSL streams:** Start measurement in Complete Euler mode, check successful synchronization for multiple DOTs, and ensure local/network configuration matches the consumer.
- **Native library missing:** Follow [deployment instructions](docs/DEPLOYMENT.md) for liblsl installation or `LIBLSL_PATH` configuration.
- **Port 8080 in use:** Stop the previous server cleanly before launching a new instance.
- **Network discovery fails:** Check that hosts are on a compatible trusted network, that LSL discovery traffic is permitted, and that local-only mode is not selected.

## Repository guide

| File or directory | Purpose |
| --- | --- |
| `xsensDotServer.js` | Server entry point |
| `bleHandler.js`, `sensorServer.js`, `syncManager.js` | BLE acquisition, state machine, synchronization and CSV |
| `lslPublisher.js` | Direct LSL publishing and timestamp mapping |
| `webGuiHandler.js`, `communication.js`, `index.html`, `styleSheet.css` | Web server and browser interface |
| `run_movella.sh`, `setup_dependencies.sh`, `install_launcher.sh` | Deployment and startup |
| `lsl_local.cfg`, `check_local_lsl.py` | Local LSL configuration and diagnostics |
| `docs/DEPLOYMENT.md` | Detailed deployment and acceptance checks |
| `documentation/` | Historical upstream architecture PDFs; not current deployment instructions |
| `AGENTS.md` | Development guidance |

## Attribution and feedback

Based on the original [Xsens DOT Server](https://github.com/xsens/xsens_dot_server). Original source notices and upstream technical references are retained. See upstream terms and applicable third-party licenses before redistribution; this fork does not add a new license grant.

Report fork-specific problems through [this repository's issues](https://github.com/gabrielworcester-del/XDS_js/issues). Include the OS, Node version, DOT firmware, number of sensors, launch mode and relevant logs (remove identifying sensor addresses if appropriate).
