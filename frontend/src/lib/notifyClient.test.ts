import { afterEach, expect, test, vi } from 'vitest';
import type { AlertEvent } from './alertEngine';
import { notifyAlert } from './notifyClient';

const event: AlertEvent = {
  id: 'e1',
  timestamp: 1000,
  recipientId: 'primary',
  ruleId: 'sensor-1',
  source: 'SENSOR_1',
  transition: 'HIGH',
  destination: '+15005550006',
  message: 'Temperature high.',
  celsius: 40,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test('maps a 2xx response to ok', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ status: 'sent', providerId: 'SM1' }), { status: 200 })),
  );
  expect(await notifyAlert(event)).toEqual({ ok: true, status: 'sent' });
});

test('maps a 4xx response to a failure with a reason', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ status: 'failed', error: 'destination is not E.164' }), { status: 400 })),
  );
  expect(await notifyAlert(event)).toEqual({
    ok: false,
    status: 'failed',
    reason: 'destination is not E.164',
  });
});

test('maps a thrown fetch to "unreachable"', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('connection refused'); }));
  expect(await notifyAlert(event)).toEqual({ ok: false, status: 'unreachable' });
});
