#!/usr/bin/env python3
"""Patch XDS_js for one unsynchronized Movella DOT -> LSL.
Run from the XDS_js repository directory: python3 movella_lsl_fix.py
Does not modify hardware-synchronized multi-DOT logic.
"""
from pathlib import Path
import sys

root = Path.cwd()
ble_file = root / 'bleHandler.js'
lsl_file = root / 'lslPublisher.js'
for file in (ble_file, lsl_file):
    if not file.is_file():
        sys.exit(f'ERROR: {file} not found. Run from your XDS_js directory.')

ble = ble_file.read_text()
lsl = lsl_file.read_text()


def replace_once(text, old, new, name):
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{name}: expected exactly 1 match, found {n}. No files changed.')
    return text.replace(old, new, 1)

try:
    new_ble = replace_once(ble,
'''                // Only publish hardware-synchronized Complete Euler measurements.
                // No UDP socket, disk read, or independent sensor timestamps.
                if (bleHandler.lslPublisher && bleHandler.isSyncingEnabled &&
                    measuringPayloadId === MEASURING_PAYLOAD_TYPE_COMPLETE_EULER)
                {
                    try
                    {
                        bleHandler.lslPublisher.onMeasurement(decoded);
                    }''',
'''                // Publish Complete Euler in either mode: synchronized sensor clock,
                // or unsynchronized single-DOT with BLE arrival time.
                if (bleHandler.lslPublisher &&
                    measuringPayloadId === MEASURING_PAYLOAD_TYPE_COMPLETE_EULER)
                {
                    try
                    {
                        bleHandler.lslPublisher.onMeasurement(
                            decoded, !bleHandler.isSyncingEnabled
                        );
                    }''', 'BLE measurement dispatch')

    new_lsl = replace_once(lsl,
'''    createSensorOutlet(address) {
        if (this.outlets.has(address)) return this.outlets.get(address);
        if (!this.syncReady || !this.syncedAddresses.has(address)) return null;
        if (this.outlets.size >= this.maxSensors) return null;''',
'''    createSensorOutlet(address, unsynced = false) {
        if (this.outlets.has(address)) return this.outlets.get(address);
        if (!unsynced && (!this.syncReady || !this.syncedAddresses.has(address))) return null;
        // Only one unsynchronized sensor; do not imply multi-sensor clock alignment.
        if (unsynced && this.outlets.size > 0) return null;
        if (this.outlets.size >= this.maxSensors) return null;''', 'LSL outlet guard')

    new_lsl = replace_once(new_lsl,
'''            appendValue(desc, 'root_address', this.rootAddress);
            appendValue(desc, 'payload', 'Complete Euler (ID 16)');
            appendValue(desc, 'timebase', 'root-synchronized SampleTimeFine (microseconds)');
            appendValue(desc, 'lsl_time_note',
                'Shared sensor-time mapping anchored at first packet arrival; absolute offset includes initial BLE delay');''',
'''            appendValue(desc, 'root_address', unsynced ? 'none' : this.rootAddress);
            appendValue(desc, 'payload', 'Complete Euler (ID 16)');
            appendValue(desc, 'timebase', unsynced
                ? 'host-derived CSV timestamp; LSL clock at BLE packet arrival'
                : 'root-synchronized SampleTimeFine (microseconds)');
            appendValue(desc, 'lsl_time_note', unsynced
                ? 'Unsynchronized single DOT; arrival timestamp includes BLE delay and jitter'
                : 'Shared sensor-time mapping anchored at first packet arrival; absolute offset includes initial BLE delay');''', 'LSL metadata')

    start = new_lsl.find('    onMeasurement(p) {')
    end = new_lsl.find('\n    onDisconnect(address) {', start)
    if start < 0 or end < 0:
        raise RuntimeError('LSL measurement function not found in expected form. No files changed.')
    new_lsl = new_lsl[:start] + '''    onMeasurement(p, unsynced = false) {
        if (this.failed || !p || !p.address) return;
        if (!unsynced && (!this.syncReady || !this.syncedAddresses.has(p.address))) return;

        // Synchronized sensor time is uint32 microseconds; when sync is off,
        // the existing CSV pathway uses a derived host time instead.
        if (!Number.isFinite(p.timestamp)) return;
        if (!unsynced && (!Number.isInteger(p.timestamp) ||
            p.timestamp < 0 || p.timestamp > 0xFFFFFFFF)) return;

        const values = [p.timestamp, p.euler_x, p.euler_y, p.euler_z,
                        p.freeAcc_x, p.freeAcc_y, p.freeAcc_z];
        if (!values.every(Number.isFinite)) return;

        const outlet = this.createSensorOutlet(p.address, unsynced);
        if (!outlet) return;
        const lslTime = unsynced ? localClock() : this.toLslTime(p.address, p.timestamp);
        if (lslTime === null) return;
        const rc = pushSample(outlet, Float64Array.from(values), lslTime, 1);
        if (rc !== 0) throw new Error('lsl_push_sample_dtp returned ' + rc);
    }
''' + new_lsl[end:]
except RuntimeError as exc:
    sys.exit(f'ERROR: {exc}')

for file in (ble_file, lsl_file):
    backup = file.with_name(file.name + '.before_single_dot_lsl.bak')
    if backup.exists():
        sys.exit(f'ERROR: Backup already exists: {backup}. No files changed.')

for file in (ble_file, lsl_file):
    backup = file.with_name(file.name + '.before_single_dot_lsl.bak')
    backup.write_bytes(file.read_bytes())

ble_file.write_text(new_ble)
lsl_file.write_text(new_lsl)
print('SUCCESS: Patched bleHandler.js and lslPublisher.js')
print('Original copies saved as *.before_single_dot_lsl.bak')
print('Next: node --check bleHandler.js && node --check lslPublisher.js')
