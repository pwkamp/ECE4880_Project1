import assert from 'node:assert/strict';
import { test } from 'vitest';
import type { SensorId, SwitchState, ThermometerFrame } from '../datasource/types';
import {
  DEFAULT_ALERT_CONFIG,
  EMPTY_LATCH,
  evaluateAlerts,
  type AlertLatch,
} from './alerts';
import { readoutFor } from './readout';

function frame(opts: {
  switchState?: SwitchState;
  s1?: number | null;
  s2?: number | null;
  s1connected?: boolean;
  s1enabled?: boolean;
}): ThermometerFrame {
  const mk = (id: SensorId, celsius: number | null, connected = true, enabled = true) => ({
    sensorId: id,
    celsius,
    connected,
    enabled,
  });
  const s1 = 's1' in opts ? (opts.s1 as number | null) : 22;
  const s2 = 's2' in opts ? (opts.s2 as number | null) : 22;
  return {
    timestamp: 1000,
    switchState: opts.switchState ?? 'on',
    readings: {
      1: mk(1, s1, opts.s1connected ?? true, opts.s1enabled ?? true),
      2: mk(2, s2),
    },
  };
}

test('readout: switch off => no data for both sensors', () => {
  const f = frame({ switchState: 'off' });
  assert.equal(readoutFor(f, 1).kind, 'no-data');
  assert.equal(readoutFor(f, 2).kind, 'no-data');
});

test('readout: unplugged sensor reported before display-off', () => {
  const f = frame({ s1connected: false, s1enabled: false, s1: null });
  assert.equal(readoutFor(f, 1).kind, 'unplugged');
});

test('readout: live value passes through', () => {
  const r = readoutFor(frame({ s1: 24.5 }), 1);
  assert.deepEqual(r, { kind: 'ok', celsius: 24.5 });
});

test('alerts: one alert per crossing, not per second', () => {
  const cfg = { ...DEFAULT_ALERT_CONFIG, maxC: 30, minC: 10 };
  let latch: AlertLatch = EMPTY_LATCH;

  let r = evaluateAlerts(frame({ s1: 31 }), cfg, latch);
  assert.equal(r.fired.length, 1, 'fires on crossing');
  latch = r.latch;

  r = evaluateAlerts(frame({ s1: 32 }), cfg, latch);
  assert.equal(r.fired.length, 0, 'no repeat while still exceeded');
  latch = r.latch;

  r = evaluateAlerts(frame({ s1: 25 }), cfg, latch);
  assert.equal(r.fired.length, 0, 'no alert on return to band');
  latch = r.latch;

  r = evaluateAlerts(frame({ s1: 33 }), cfg, latch);
  assert.equal(r.fired.length, 1, 're-crossing fires again');
});

test('alerts: missing data does not clear the latch', () => {
  const cfg = { ...DEFAULT_ALERT_CONFIG, maxC: 30, minC: 10 };
  let r = evaluateAlerts(frame({ s1: 31 }), cfg, EMPTY_LATCH);
  assert.equal(r.fired.length, 1);

  r = evaluateAlerts(frame({ s1: null }), cfg, r.latch);
  assert.equal(r.fired.length, 0);

  // still exceeded when data returns -> not a new crossing
  r = evaluateAlerts(frame({ s1: 31 }), cfg, r.latch);
  assert.equal(r.fired.length, 0);
});

test('alerts: disabled config never fires', () => {
  const cfg = { ...DEFAULT_ALERT_CONFIG, enabled: false, maxC: 10 };
  const r = evaluateAlerts(frame({ s1: 40, s2: 40 }), cfg, EMPTY_LATCH);
  assert.equal(r.fired.length, 0);
});
