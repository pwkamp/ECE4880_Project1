import { expect, test, vi } from 'vitest';
import { BleApiClient } from './bleClient';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

test('scan posts to the BLE connector and returns devices', async () => {
  const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe('/api/v1/ble/scan');
    return jsonResponse({
      devices: [{ name: 'Thermometer-1', address: 'AA:BB:CC:DD:EE:FF', rssi: -40 }],
    });
  });
  const client = new BleApiClient({ fetchFn });
  const devices = await client.scan();
  expect(fetchFn).toHaveBeenCalledWith(
    '/api/v1/ble/scan',
    expect.objectContaining({ method: 'POST' }),
  );
  expect(devices).toEqual([
    { name: 'Thermometer-1', address: 'AA:BB:CC:DD:EE:FF', rssi: -40 },
  ]);
});

test('an absolute BLE base targets the native Windows backend', async () => {
  const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
    expect(String(input)).toBe('http://127.0.0.1:8000/api/v1/ble/status');
    return jsonResponse({ phase: 'IDLE' });
  });
  const client = new BleApiClient({
    fetchFn,
    bleBase: 'http://127.0.0.1:8000/api/v1/ble',
  });

  await client.getStatus();
  expect(fetchFn).toHaveBeenCalledOnce();
});

test('connect sends address and optional passkey', async () => {
  const fetchFn = vi.fn(async () =>
    jsonResponse({ operation_id: 'op-1', state: 'RUNNING' }, 202),
  );
  const client = new BleApiClient({ fetchFn });
  await client.connect('AA:BB:CC:DD:EE:FF', '123456');
  expect(fetchFn).toHaveBeenCalledWith(
    '/api/v1/ble/connect',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ address: 'AA:BB:CC:DD:EE:FF', passkey: '123456' }),
    }),
  );
});

test('setDisplay PUTs enabled for a sensor id', async () => {
  const fetchFn = vi.fn(async () => jsonResponse({ enabled: false }));
  const client = new BleApiClient({ fetchFn });
  expect(await client.setDisplay(2, false)).toEqual({ enabled: false });
  expect(fetchFn).toHaveBeenCalledWith(
    '/api/v1/ble/displays/2',
    expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ enabled: false }),
    }),
  );
});

test('disconnect explicitly posts to the backend', async () => {
  const fetchFn = vi.fn(async () => jsonResponse({ disconnected: true }));
  const client = new BleApiClient({ fetchFn });
  await client.disconnect();
  expect(fetchFn).toHaveBeenCalledWith(
    '/api/v1/ble/disconnect',
    expect.objectContaining({ method: 'POST' }),
  );
});

test('getSamplesLatest returns null when the DB reader is not configured', async () => {
  const fetchFn = vi.fn(async (input: RequestInfo | URL) => {
    if (String(input).startsWith('/api/samples')) {
      return jsonResponse({ configured: false });
    }
    return jsonResponse({ error: 'unexpected' }, 500);
  });
  const client = new BleApiClient({ fetchFn });
  expect(await client.getSamplesLatest()).toBeNull();
  expect(await client.getSamplesHistory(300)).toEqual([]);
});

test('getSamplesHistory maps configured DB rows', async () => {
  const row = {
    observed_at_utc: '2026-09-09T16:00:00Z',
    sensor1_c: 20,
    sensor1_status: 'VALID',
    sensor2_c: 21,
    sensor2_status: 'VALID',
  };
  const fetchFn = vi.fn(async () => jsonResponse({ configured: true, rows: [row] }));
  const client = new BleApiClient({ fetchFn });
  expect(await client.getSamplesHistory(300)).toEqual([row]);
});
