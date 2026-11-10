#!/usr/bin/env python3
"""Allow Movella DOT synchronization when the GUI state is stuck in Scanning.

Usage (from ~/XDS_js): python3 patch_movella_scan_sync_gate_v4.py
Only changes sensorServer.js. Makes a timestamped backup. Safe to rerun.
"""
from pathlib import Path
from datetime import datetime
import re
import shutil
import sys

path = Path('sensorServer.js')
if not path.is_file():
    sys.exit('ERROR: Run this from ~/XDS_js (sensorServer.js not found).')
src = path.read_text()

# This is a deliberately narrow patch. Do not rewrite existing idle transition,
# BLE connection handler, native sync-manager, or LSL publisher.
if re.search(r"stateName:\s*'Scanning',\s*eventName:\s*'startSyncing'", src):
    print('Already applied: Scanning/startSyncing transition exists. No changes made.')
    sys.exit(0)

pattern = re.compile(
    r"(?m)^(?P<indent>[ \t]*)\{\s*\n"
    r"[ \t]*stateName:\s*'Idle',\s*\n"
    r"[ \t]*eventName:\s*'startSyncing',"
)
matches = list(pattern.finditer(src))
if len(matches) != 1:
    sys.exit(f'ERROR: Expected exactly one Idle/startSyncing transition; found {len(matches)}. No changes made.')

block = """    // Allow synchronization even when a missed scan-stop callback has left
    // the global GUI state at Scanning. This does not bypass DOT sync checks.
    {
        stateName: 'Scanning',
        eventName: 'startSyncing',
        nextState: 'Syncing',
        transFunc:function( component, parameters )
        {
            const scanning = component.ble._bleScanActive === true;
            console.log('[STATE] startSyncing accepted from Scanning; scanActive=', scanning);
            if (scanning)
            {
                component.ble.stopScanning();
                // Give Noble/BlueZ time to settle before sync control writes.
                setTimeout(function() { component.syncManager.startSyncing(); }, 300);
            }
            else
            {
                component.syncManager.startSyncing();
            }
        }
    },
"""
where = matches[0].start()
patched = src[:where] + block + src[where:]
backup = path.with_name(path.name + '.bak_scan_sync_v4_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
shutil.copy2(path, backup)
try:
    path.write_text(patched)
except Exception:
    shutil.copy2(backup, path)
    raise
print('Updated:', path)
print('Backup:', backup)
print('Next: node --check sensorServer.js')
print('Stop Node before applying, then restart it after syntax check.')
