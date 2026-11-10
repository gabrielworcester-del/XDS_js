#!/usr/bin/env python3
"""Minimal diagnostic patch for two Movella DOT connections.

Run from the XDS_js repository root:
    python3 patch_movella_two_dot_connections.py

Creates timestamped backups and only patches expected source snippets.
"""
from pathlib import Path
from datetime import datetime
import shutil

ROOT = Path(__file__).resolve().parent
if not (ROOT / 'sensorServer.js').exists():
    ROOT = Path.cwd()

def change(filename, old, new):
    path = ROOT / filename
    if not path.exists():
        raise SystemExit(f'Missing {path}; run from XDS_js')
    data = path.read_text()
    if new in data:
        print(f'[SKIP] {filename}: patch already present')
        return
    n = data.count(old)
    if n != 1:
        raise SystemExit(f'[STOP] Expected one insertion point in {filename}, found {n}; no change to this file')
    backup = path.with_name(f'{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}')
    shutil.copy2(path, backup)
    path.write_text(data.replace(old, new, 1))
    print(f'[OK] {filename} | backup: {backup.name}')

# A user cancellation can race with the asynchronous BLE and GUI callbacks.
# A stop event for an already-idle sensor should not be treated as a fatal state error.
old = "    // -- Connecting --\n"
new = """    // -- Connecting --
    // A delayed GUI cancel/stop can arrive after a connection state has
    // already returned to Idle. Treat it as a stale no-op, not an error.
    {
        stateName: 'Idle',
        eventName: 'stopConnectingSensors',
        nextState: 'Idle',
        transFunc: function(component, parameters)
        {
            console.log('[STATE] Ignored late stopConnectingSensors for',
                parameters && parameters.addresses && parameters.addresses[0]);
        }
    },
"""
change('sensorServer.js', old, new)

old = """    connectSensor( sensor )
    {
        var bleHandler = this;
"""
new = """    connectSensor( sensor )
    {
        var bleHandler = this;
        console.log('[BLE] CONNECT request', sensor.address,
            'peripheralState=', sensor.state,
            'activeConnections=', globalConnectedSensors.map(s => s.address).join(','));
"""
change('bleHandler.js', old, new)

old = """        sensor.connect( function(error)
        {
            if( error )
"""
new = """        sensor.connect( function(error)
        {
            console.log('[BLE] CONNECT result', sensor.address,
                'error=', error ? String(error) : 'none',
                'peripheralState=', sensor.state);
            if( error )
"""
change('bleHandler.js', old, new)

print('Done. Check syntax with: node --check sensorServer.js && node --check bleHandler.js')
