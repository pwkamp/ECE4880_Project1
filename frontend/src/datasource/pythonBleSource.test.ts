import { afterEach, expect, test, vi } from 'vitest';
import type { BleApiClient } from './bleClient';
import type { BleStatus, SampleRow } from './bleMap';
import { PythonBleSource } from './pythonBleSource';
import { supportsBle } from './types';

const statusReady: BleStatus = {
  phase: 'CONNECTED',
  connected: true,
  ready: true,
  target: { name: 'Thermometer-1', address: 'AA:BB:CC:DD:EE:FF' },
  last_error: null,
};

const dbRow: SampleRow = {
  observed_at_utc: new Date().toISOString(),
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
    setDisplay: vi.fn(async (_id: number, enabled: boolean) => ({ enabled })),
    getSamplesLatest: vi.fn(async () => null),
    getSamplesHistory: vi.fn(async () => []),
    ...overrides,
  } as unknown as BleApiClient;
}

afterEach(() => {
  vi.useRealTimers();
});

test('uses the MySQL sample for the current reading', async () => {
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

test('does not request BLE current when the database is empty', async () => {
  const client = stubClient();
  const source = new PythonBleSource({ client, intervalMs: 1_000 });
  source.start();
  await vi.waitFor(() => {
    expect(client.getSamplesLatest).toHaveBeenCalled();
  });
  expect(source.getFrame().readings[1].celsius).toBeNull();
  expect(client.getSamplesHistory).toHaveBeenCalled();
  source.stop();
});

test('setSensorEnabled waits for the device confirmation', async () => {
  const client = stubClient();
  const source = new PythonBleSource({ client, intervalMs: 60_000 });
  await source.setSensorEnabled(1, false);
  expect(client.setDisplay).toHaveBeenCalledWith(1, false);
  expect(source.getFrame().readings[1].enabled).toBe(false);
});

test('a stale status poll cannot undo a confirmed display command', async () => {
  const client = stubClient({
    getStatus: vi.fn(async () => ({
      ...statusReady,
      displays: [{ sensor_id: 1, enabled: true }],
    })),
    getSamplesLatest: vi.fn(async () => dbRow),
  });
  const source = new PythonBleSource({ client, intervalMs: 50 });
  source.start();
  await vi.waitFor(() => expect(client.getSamplesLatest).toHaveBeenCalled());
  await source.setSensorEnabled(1, false);
  await vi.waitFor(() => expect(client.getStatus).toHaveBeenCalledTimes(3));
  expect(source.getFrame().readings[1].enabled).toBe(false);
  source.stop();
});

test('a failed display command leaves the confirmed state unchanged', async () => {
  const client = stubClient({
    setDisplay: vi.fn(async () => { throw new Error('BLE command timed out'); }),
    getSamplesLatest: vi.fn(async () => dbRow),
  });
  const source = new PythonBleSource({ client, intervalMs: 60_000 });
  source.start();
  await vi.waitFor(() => expect(client.getSamplesLatest).toHaveBeenCalled());
  await expect(source.setSensorEnabled(1, false)).rejects.toThrow('timed out');
  expect(source.getFrame().readings[1].enabled).toBe(true);
  source.stop();
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

test('loads all 300 pre-connection seconds from MySQL within the recovery window', async () => {
  const now = Date.now();
  const rows: SampleRow[] = Array.from({ length: 300 }, (_, index) => ({
    ...dbRow,
    observed_at_utc: new Date(now - (309 - index) * 1000).toISOString(),
    sensor1_c: 17 + index / 100,
  }));
  const getSamplesHistory = vi.fn(async () => rows);
  const source = new PythonBleSource({
    client: stubClient({ getSamplesHistory }),
    intervalMs: 1_000,
  });

  source.start();
  await vi.waitFor(() => expect(source.getHistory(320)).toHaveLength(300));
  expect(getSamplesHistory).toHaveBeenCalledWith(320);
  expect(source.getHistory(320)[0].readings[1].celsius).toBe(17);
  expect(source.getHistory(320)[299].readings[1].celsius).toBeCloseTo(19.99);
  source.stop();
});

test('refreshes MySQL history to replace gaps after reconnection', async () => {
  const gap: SampleRow = {
    ...dbRow,
    observed_at_utc: new Date(Date.now() - 2_000).toISOString(),
    sensor1_c: null,
    sensor1_status: 'MISSING',
  };
  const recovered: SampleRow = { ...gap, sensor1_c: 20.1, sensor1_status: 'VALID' };
  const getSamplesHistory = vi.fn()
    .mockResolvedValueOnce([gap, dbRow])
    .mockResolvedValue([recovered, dbRow]);
  const client = stubClient({ getSamplesHistory, getSamplesLatest: vi.fn(async () => dbRow) });
  const source = new PythonBleSource({ client, intervalMs: 1_000 });
  source.start();
  await vi.waitFor(() => expect(source.getHistory(300)[0]?.readings[1].celsius).toBeNull());
  await vi.waitFor(
    () => expect(source.getHistory(300)[0]?.readings[1].celsius).toBe(20.1),
    { timeout: 5_000 },
  );
  source.stop();
});
