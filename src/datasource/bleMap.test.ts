import { expect, test } from 'vitest';
import {
  frameFromBle,
  frameFromSample,
  type BleCurrent,
  type BleStatus,
  type SampleRow,
} from './bleMap';

const readyStatus: BleStatus = {
  phase: 'CONNECTED',
  connected: true,
  ready: true,
  target: { name: 'Thermometer-AA11', address: 'AA:BB:CC:DD:EE:FF' },
  last_error: null,
};

const liveCurrent: BleCurrent = {
  available: true,
  received_at_utc: '2026-09-09T16:00:00Z',
  snapshot: {
    sensors: [
      {
        sensor_id: 1,
        temperature_c: 21.5,
        visible_state: 'ON',
        display_enabled: true,
        connected: true,
      },
      {
        sensor_id: 2,
        temperature_c: null,
        visible_state: 'DISCONNECTED',
        display_enabled: false,
        connected: false,
      },
    ],
  },
  error: null,
};

test('BLE current maps sensor 1 live and sensor 2 unplugged', () => {
  const frame = frameFromBle(liveCurrent, readyStatus, 1_700_000_000_000);
  expect(frame.switchState).toBe('on');
  expect(frame.timestamp).toBe(Date.parse('2026-09-09T16:00:00Z'));
  expect(frame.readings[1]).toEqual({
    sensorId: 1,
    celsius: 21.5,
    connected: true,
    enabled: true,
  });
  expect(frame.readings[2]).toEqual({
    sensorId: 2,
    celsius: null,
    connected: false,
    enabled: false,
  });
});

test('display off keeps the probe connected but clears celsius', () => {
  const current: BleCurrent = {
    available: true,
    received_at_utc: '2026-09-09T16:00:00Z',
    snapshot: {
      sensors: [
        {
          sensor_id: 1,
          temperature_c: 22,
          visible_state: 'OFF',
          display_enabled: false,
          connected: true,
        },
        {
          sensor_id: 2,
          temperature_c: 23,
          visible_state: 'ON',
          display_enabled: true,
          connected: true,
        },
      ],
    },
    error: null,
  };
  const frame = frameFromBle(current, readyStatus, 0);
  expect(frame.readings[1].connected).toBe(true);
  expect(frame.readings[1].enabled).toBe(false);
  expect(frame.readings[1].celsius).toBeNull();
  expect(frame.readings[2].celsius).toBe(23);
});

test('unavailable BLE current is treated as switch-off / no data', () => {
  const frame = frameFromBle(
    { available: false, received_at_utc: null, snapshot: null, error: 'offline' },
    { ...readyStatus, ready: false, connected: false, phase: 'DISCOVERING' },
    42,
  );
  expect(frame.switchState).toBe('off');
  expect(frame.timestamp).toBe(42);
  expect(frame.readings[1].celsius).toBeNull();
  expect(frame.readings[2].celsius).toBeNull();
});

test('DB VALID rows supply temperatures; DISCONNECTED is unplugged', () => {
  const row: SampleRow = {
    observed_at_utc: '2026-09-09T16:00:01Z',
    sensor1_c: 19.25,
    sensor1_status: 'VALID',
    sensor2_c: null,
    sensor2_status: 'DISCONNECTED',
  };
  const frame = frameFromSample(row, { 1: true, 2: true }, 'on');
  expect(frame.timestamp).toBe(Date.parse(row.observed_at_utc));
  expect(frame.readings[1].celsius).toBe(19.25);
  expect(frame.readings[1].connected).toBe(true);
  expect(frame.readings[2].celsius).toBeNull();
  expect(frame.readings[2].connected).toBe(false);
});

test('DB MISSING/NOT_RETRIEVED clear celsius without marking unplugged', () => {
  const row: SampleRow = {
    observed_at_utc: '2026-09-09T16:00:02Z',
    sensor1_c: null,
    sensor1_status: 'MISSING',
    sensor2_c: null,
    sensor2_status: 'NOT_RETRIEVED',
  };
  const frame = frameFromSample(row, { 1: true, 2: false }, 'on');
  expect(frame.readings[1].connected).toBe(true);
  expect(frame.readings[1].celsius).toBeNull();
  expect(frame.readings[2].enabled).toBe(false);
  expect(frame.readings[2].celsius).toBeNull();
});
