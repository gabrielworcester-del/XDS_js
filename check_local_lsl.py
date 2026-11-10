#!/usr/bin/env python3
"""Run with LSLAPICFG set to lsl_local.cfg, on the Raspberry Pi."""
import os
import sys

if not os.environ.get('LSLAPICFG'):
    sys.exit('Set LSLAPICFG to the absolute path of lsl_local.cfg first.')
try:
    from pylsl import resolve_streams, StreamInlet
except ImportError:
    sys.exit('Install pylsl in your Python environment: python3 -m pip install pylsl')

streams = [s for s in resolve_streams(wait_time=5.0) if s.name().startswith('Xsens_DOT_')]
if not streams:
    sys.exit('No Xsens_DOT streams discovered. Start measuring in the server GUI first.')
print('Found:', len(streams), 'DOT stream(s)')
for stream in streams:
    print(' ', stream.name(), '| channels:', stream.channel_count())
    inlet = StreamInlet(stream)
    sample, ts = inlet.pull_sample(timeout=5.0)
    if sample is None:
        print('   No sample within 5 seconds (check measurement state).')
    else:
        print('   LSL timestamp:', ts, '| first 3 channels:', sample[:3])
    inlet.close_stream()
