import { afterEach, expect, test, vi } from 'vitest';
import type { BleApiClient } from './bleClient';
import type { BleCurrent, BleStatus, SampleRow } from './bleMap';
import { PythonBleSource } from './pythonBleSource';
import { supportsBle } from './types';

const statusReady: BleStatus = {
  phase: 'CONNECTED',
  connected: true,
  ready: true,
  target: { name: 'Thermometer-1', address: 'AA:BB:CC:DD:EE:FF' },
  last_error: null,
};

const bleLive: BleCurrent = {
  available: true,
  received_at_utc: '2026-09-09T16:00:00.000Z',
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
        temperature_c: 23.0,
        visible_state: 'ON',
        display_enabled: true,
        connected: true,
      },
    ],
  },
  error: null,
};

const dbRow: SampleRow = {
  observed_at_utc: '2026-09-09T16:00:05.000Z',
  sensor1_c: 18.5,
  sensor1_status: 'VALID',
  sensor2_c: 19.0,
  sensor2_status: 'VALID',
};

function stubClient(overrides: Partial<BleApiClient> = {}): BleApiClient {
  return {
    scan: vi.fn(async () => []),
    connect: vi.fn(async () => undefined),
    disconnect: vi.fn(async () => undefined),
    reconnect: vi.fn(async () => undefined),
    getStatus: vi.fn(async () => statusReady),
    getCurrent: vi.fn(async () => bleLive),
    setDisplay: vi.fn(async () => undefined),
    getSamplesLatest: vi.fn(async () => null),
    getSamplesHistory: vi.fn(async () => []),
    ...overrides,
  } as unknown as BleApiClient;
}

afterEach(() => {
  vi.useRealTimers();
});

test('prefers a DB sample over the live BLE snapshot', async () => {
  const client = stubClient({
    getSamplesLatest: vi.fn(async () => dbRow),
  });
  const source = new PythonBleSource({ client, intervalMs: 1_000 });
  source.start();
  await vi.waitFor(() => {
    expect(source.getFrame().readings[1].celsius).toBe(18.5);
  });
  source.stop();
});

test('falls back to BLE current when the DB reader is empty', async () => {
  const client = stubClient();
  const source = new PythonBleSource({ client, intervalMs: 1_000 });
  source.start();
  await vi.waitFor(() => {
    expect(source.getFrame().readings[1].celsius).toBe(21.5);
  });
  source.stop();
});

test('setSensorEnabled forwards to the BLE display endpoint', async () => {
  const client = stubClient();
  const source = new PythonBleSource({ client, intervalMs: 60_000 });
  source.setSensorEnabled(1, false);
  await vi.waitFor(() => {
    expect(client.setDisplay).toHaveBeenCalledWith(1, false);
  });
});

test('scan/connect are exposed for the device panel', async () => {
  const client = stubClient({
    scan: vi.fn(async () => [
      { name: 'Thermometer-1', address: 'AA:BB:CC:DD:EE:FF', rssi: -40 },
    ]),
  });
  const source = new PythonBleSource({ client, intervalMs: 60_000 });
  expect(supportsBle(source)).toBe(true);
  expect(await source.scan()).toEqual([
    { name: 'Thermometer-1', address: 'AA:BB:CC:DD:EE:FF', rssi: -40 },
  ]);
  await source.connect('AA:BB:CC:DD:EE:FF', '123456');
  expect(client.connect).toHaveBeenCalledWith('AA:BB:CC:DD:EE:FF', '123456');
});

test('getHistory maps DB rows when the table is populated', async () => {
  const client = stubClient({
    getSamplesHistory: vi.fn(async () => [dbRow]),
    getSamplesLatest: vi.fn(async () => dbRow),
  });
  const source = new PythonBleSource({ client, intervalMs: 1_000 });
  source.start();
  await vi.waitFor(() => {
    expect(source.getHistory(300)).toHaveLength(1);
  });
  expect(source.getHistory(300)[0].readings[1].celsius).toBe(18.5);
  source.stop();
});
