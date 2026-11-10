#!/usr/bin/env python3
"""Patch the existing Movella DOT project to test hung second BLE connections.

Run from ~/XDS_js: python3 patch_movella_ble_connect_v2.py
Safe to rerun; creates backups; fails if code differs from expected patch v1.
Does not modify LSL or synchronization logic.
"""
from pathlib import Path
from datetime import datetime
import shutil

root = Path.cwd()
path = root / 'bleHandler.js'
if not path.is_file():
    raise SystemExit('Run this script from the XDS_js directory containing bleHandler.js')
src = path.read_text()
if '[BLE-V2] Timeout waiting for Noble connection callback' in src:
    print('Already patched (v2); no changes made')
    raise SystemExit(0)

def replace_one(old, new):
    global src
    n = src.count(old)
    if n != 1:
        raise SystemExit(f'Expected exactly one anchor, found {n}: {old[:100]!r}. No files changed.')
    src = src.replace(old, new, 1)

replace_one("        this.central = require('@abandonware/noble');", """        this.central = require('@abandonware/noble');
        this._bleScanActive = false;
        this._pendingConnections = new Set();""")
replace_one("""        central.on( 'scanStart', function()
        {
            bleHandler.sendBleEvent( 'bleScanningStarted' );
        });""", """        central.on( 'scanStart', function()
        {
            bleHandler._bleScanActive = true;
            console.log('[BLE-V2] Scan started');
            bleHandler.sendBleEvent( 'bleScanningStarted' );
        });""")
replace_one("""        central.on( 'scanStop', function()
        {
            bleHandler.sendBleEvent( 'bleScanningStopped' );
        });""", """        central.on( 'scanStop', function()
        {
            bleHandler._bleScanActive = false;
            console.log('[BLE-V2] Scan stopped');
            bleHandler.sendBleEvent( 'bleScanningStopped' );
        });""")

# Keep existing debug instrumentation from patch 1 intact. Replace just the BLE call,
# and preserve all original connection and service-discovery callbacks.
replace_one("""        sensor.removeAllListeners();
        sensor.connect( function(error)
        {
            console.log('[BLE] CONNECT result', sensor.address,
                'error=', error ? String(error) : 'none',
                'peripheralState=', sensor.state);
""", """        // Only one outstanding connect attempt per peripheral.
        if (this._pendingConnections.has(sensor.address)) {
            console.warn('[BLE-V2] Duplicate CONNECT ignored:', sensor.address,
                'peripheralState=', sensor.state);
            return;
        }
        if (sensor.state === 'connecting' || sensor.state === 'disconnecting') {
            console.warn('[BLE-V2] CONNECT deferred: peripheral is', sensor.state,
                sensor.address, '(restart server after a hung attempt)');
            return;
        }
        if (sensor.state === 'connected') {
            console.log('[BLE-V2] Already connected:', sensor.address);
            return;
        }
        this._pendingConnections.add(sensor.address);
        const scanWasActive = this._bleScanActive;
        console.log('[BLE-V2] Preparing connection', sensor.address,
            'scanActive=', scanWasActive);
        // Some HCI controllers cannot establish a connection while actively scanning.
        // Keep the pause small; avoid changing the existing GUI connection workflow.
        if (scanWasActive) {
            console.log('[BLE-V2] Stopping scan before connection');
            this.central.stopScanning();
        }
        const attemptStarted = Date.now();
        let completed = false;
        const warningTimer = setTimeout(() => {
            if (!completed) {
                console.error('[BLE-V2] Timeout waiting for Noble connection callback',
                    sensor.address, 'elapsedMs=', Date.now() - attemptStarted,
                    'peripheralState=', sensor.state,
                    'scanActive=', bleHandler._bleScanActive);
                console.error('[BLE-V2] Run sudo btmon during next attempt to inspect HCI events');
                // Do not forcibly disconnect or cancel: we are collecting diagnostics.
            }
        }, 12000);
        setTimeout(() => {
            // removeAllListeners is retained from original server for now.
            sensor.removeAllListeners();
            try {
                sensor.connect(function(error)
                {
                    completed = true;
                    clearTimeout(warningTimer);
                    bleHandler._pendingConnections.delete(sensor.address);
                    console.log('[BLE] CONNECT result', sensor.address,
                        'error=', error ? String(error) : 'none',
                        'peripheralState=', sensor.state,
                        'elapsedMs=', Date.now() - attemptStarted);
""")
# Close the new try/catch / timeout callback around original connect call
replace_one("""            });
        });
    }

    // -----------------------------------------------------------------------------------
    // -- Send BLE event --""", """            });
                });
            } catch (error) {
                completed = true;
                clearTimeout(warningTimer);
                bleHandler._pendingConnections.delete(sensor.address);
                console.error('[BLE-V2] connect threw:', error);
                bleHandler.sendBleEvent('bleSensorError', {sensor: sensor, error: error});
            }
        }, scanWasActive ? 500 : 150);
    }

    // -----------------------------------------------------------------------------------
    // -- Send BLE event --""")

backup = path.with_name('bleHandler.js.bak-v2-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(path, backup)
path.write_text(src)
print('Patched:', path)
print('Backup:', backup)
print('Run: node --check bleHandler.js')
print('Then: sudo NOBLE_HCI_DEVICE_ID=0 node xsensDotServer.js')
