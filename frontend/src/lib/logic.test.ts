import assert from 'node:assert/strict';
import { test } from 'vitest';
import type { SensorId, SwitchState, ThermometerFrame } from '../datasource/types';
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
