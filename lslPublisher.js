'use strict';

// Xsens DOT -> direct LSL publishing. One outlet per successfully synchronized
// sensor (up to MAX_SENSORS). Complete Euler (payload 16) only.
// Requires: npm install koffi; native liblsl accessible to the Pi's loader.

const koffi = require('koffi');
const lib = koffi.load(process.env.LIBLSL_PATH || 'liblsl.so');

// Official liblsl C API, called synchronously via Koffi.
const createInfo    = lib.func('void *lsl_create_streaminfo(const char *, const char *, int, double, int, const char *)');
const destroyInfo   = lib.func('void lsl_destroy_streaminfo(void *)');
const getDesc       = lib.func('void *lsl_get_desc(void *)');
const appendChild   = lib.func('void *lsl_append_child(void *, const char *)');
const appendValue   = lib.func('void *lsl_append_child_value(void *, const char *, const char *)');
const createOutlet  = lib.func('void *lsl_create_outlet(void *, int, int)');
const destroyOutlet = lib.func('void lsl_destroy_outlet(void *)');
const pushSample    = lib.func('int lsl_push_sample_dtp(void *, const double *, double, int)');
const localClock    = lib.func('double lsl_local_clock(void)');

const MAX_SENSORS = 5;
const UINT32_MOD = 4294967296;
const HALF_MOD = UINT32_MOD / 2;
const CHANNELS = [
    ['sensor_time_us', 'microseconds'],
    ['euler_x', 'degrees'],
    ['euler_y', 'degrees'],
    ['euler_z', 'degrees'],
    ['freeAcc_x', 'm/s^2'],
    ['freeAcc_y', 'm/s^2'],
    ['freeAcc_z', 'm/s^2']
];

// Signed delta for two uint32 microsecond timestamps. Handles one rollover
// provided consecutive measurements are < 2^31 us (~35.8 min) apart.
function timestampDelta(current, previous) {
    let diff = current - previous;
    if (diff < -HALF_MOD) diff += UINT32_MOD;
    if (diff > HALF_MOD) diff -= UINT32_MOD;
    return diff;
}

class LslPublisher {
    constructor(maxSensors = MAX_SENSORS) {
        this.maxSensors = maxSensors;
        this.outlets = new Map();        // MAC -> liblsl outlet handle
        this.syncedAddresses = new Set();
        this.timeState = new Map();      // MAC -> unwrapped timestamp state
        this.rootAddress = null;
        this.syncReady = false;
        this.anchorUs = null;
        this.anchorLsl = null;
        this.failed = false;
    }

    beginSync() {
        this.closeAll();
        this.syncedAddresses.clear();
        this.timeState.clear();
        this.rootAddress = null;
        this.syncReady = false;
        this.anchorUs = null;
        this.anchorLsl = null;
        this.failed = false;
        console.log('[LSL] Waiting for successful Xsens root synchronization');
    }

    completeSync(result) {
        // No outlets may survive a new / failed synchronization attempt.
        this.closeAll();
        this.syncedAddresses.clear();
        this.timeState.clear();
        this.anchorUs = null;
        this.anchorLsl = null;
        this.syncReady = false;

        const addresses = result && result.addresses;
        if (this.failed || !result || result.isAllSuccess !== true ||
            !Array.isArray(addresses) || addresses.length < 1 ||
            addresses.length > this.maxSensors ||
            addresses.some(a => typeof a !== 'string' || !a) ||
            new Set(addresses).size !== addresses.length ||
            typeof result.rootAddress !== 'string' ||
            !addresses.includes(result.rootAddress)) {
            console.warn('[LSL] Synchronization failed / invalid group / more than five sensors; not publishing');
            return false;
        }

        this.rootAddress = result.rootAddress;
        this.syncedAddresses = new Set(addresses);
        this.syncReady = true;
        console.log('[LSL] Root:', this.rootAddress,
                    '| synchronized DOTs:', addresses.length,
                    '| outlets created when Euler data starts');
        return true;
    }

    createSensorOutlet(address) {
        if (this.outlets.has(address)) return this.outlets.get(address);
        if (!this.syncReady || !this.syncedAddresses.has(address)) return null;
        if (this.outlets.size >= this.maxSensors) return null;

        const safeAddress = address.replace(/[^a-zA-Z0-9]/g, '_');
        const streamName = 'Xsens_DOT_' + safeAddress;
        const info = createInfo(
            streamName, 'IMU', CHANNELS.length,
            0.0, // irregular rate (don't assume a fixed sampling rate)
            2,   // cf_double64
            'xsens-dot-euler-' + safeAddress
        );
        if (!info) throw new Error('lsl_create_streaminfo failed');

        let outlet = null;
        try {
            const desc = getDesc(info);
            appendValue(desc, 'manufacturer', 'Movella / Xsens');
            appendValue(desc, 'sensor_address', address);
            appendValue(desc, 'root_address', this.rootAddress);
            appendValue(desc, 'payload', 'Complete Euler (ID 16)');
            appendValue(desc, 'timebase', 'root-synchronized SampleTimeFine (microseconds)');
            appendValue(desc, 'lsl_time_note',
                'Shared sensor-time mapping anchored at first packet arrival; absolute offset includes initial BLE delay');
            const channels = appendChild(desc, 'channels');
            for (const [label, unit] of CHANNELS) {
                const channel = appendChild(channels, 'channel');
                appendValue(channel, 'label', label);
                appendValue(channel, 'unit', unit);
            }
            // chunk_size=0: send every sample; max_buffered=60 s
            outlet = createOutlet(info, 0, 60);
            if (!outlet) throw new Error('lsl_create_outlet failed');
        } finally {
            destroyInfo(info);
        }
        this.outlets.set(address, outlet);
        console.log('[LSL] Created', streamName);
        return outlet;
    }

    // Convert wrapped, synchronized DOT acquisition time to one shared LSL
    // timeline. All sensors share a *single* anchor, not one per sensor.
    toLslTime(address, rawUs) {
        let state = this.timeState.get(address);
        if (this.anchorUs === null) {
            this.anchorUs = rawUs;
            this.anchorLsl = localClock();
        }
        if (!state) {
            state = {
                previous: rawUs,
                unwrapped: this.anchorUs + timestampDelta(rawUs, this.anchorUs)
            };
            this.timeState.set(address, state);
        } else {
            const delta = timestampDelta(rawUs, state.previous);
            // Don't backdate a sensor's outlet on duplicate / reordered data.
            if (delta <= 0) return null;
            state.unwrapped += delta;
            state.previous = rawUs;
        }
        return this.anchorLsl + (state.unwrapped - this.anchorUs) / 1e6;
    }

    onMeasurement(p) {
        if (!this.syncReady || this.failed || !p ||
            !this.syncedAddresses.has(p.address)) return;
        // Only decoded Complete Euler data; ignore other payload modes.
        if (!Number.isInteger(p.timestamp) ||
            p.timestamp < 0 || p.timestamp > 0xFFFFFFFF) return;
        const values = [p.timestamp, p.euler_x, p.euler_y, p.euler_z,
                        p.freeAcc_x, p.freeAcc_y, p.freeAcc_z];
        if (!values.every(Number.isFinite)) return;

        const outlet = this.createSensorOutlet(p.address);
        if (!outlet) return;
        const lslTime = this.toLslTime(p.address, p.timestamp);
        if (lslTime === null) return;
        const rc = pushSample(outlet, Float64Array.from(values), lslTime, 1);
        if (rc !== 0) throw new Error('lsl_push_sample_dtp returned ' + rc);
    }

    onDisconnect(address) {
        if (!address) return;
        if (address === this.rootAddress && this.syncReady) {
            console.warn('[LSL] Root DOT disconnected: resynchronization required');
            this.beginSync();
            return;
        }
        this.syncedAddresses.delete(address);
        this.closeSensor(address);
        this.timeState.delete(address);
    }

    onMeasurementStopped(address) {
        // Disable/re-enable need not mean the hardware sync was lost.
        this.closeSensor(address);
        // Retain last sensor tick so re-enabling after a pause does not
        // incorrectly choose a new rollover epoch relative to first packet.
    }

    closeSensor(address) {
        const outlet = this.outlets.get(address);
        if (outlet) {
            this.outlets.delete(address);
            destroyOutlet(outlet);
        }
    }

    closeAll() {
        for (const address of Array.from(this.outlets.keys())) {
            this.closeSensor(address);
        }
    }

    disable(error) {
        console.error('[LSL] Publishing disabled after native error:', error);
        this.failed = true;
        this.syncReady = false;
        this.closeAll();
    }
}

module.exports = LslPublisher;
