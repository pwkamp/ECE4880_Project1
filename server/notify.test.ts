import { expect, it } from 'vitest';
import { handleNotify } from './notify.ts';
import type { SmsMessage, SmsSender } from './sms/types.ts';

const base = {
  id: 'e1',
  timestamp: 1000,
  recipientId: 'primary',
  ruleId: 'sensor-1',
  source: 'SENSOR_1',
  transition: 'HIGH',
  destination: '+15005550006',
  message: 'Temperature high: sensor above the configured maximum.',
  celsius: 34.2,
};

function spySender(opts: { throws?: boolean } = {}) {
  const calls: SmsMessage[] = [];
  const sender: SmsSender = {
    async send(msg) {
      calls.push(msg);
      if (opts.throws) throw new Error('provider down');
      return { status: 'sent', providerId: 'SM123' };
    },
  };
  return { sender, calls };
}

it('sends an SMS for a valid HIGH event', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify(base, { sender, seen: new Set() });
  expect(out.code).toBe(200);
  expect(out.payload).toMatchObject({ status: 'sent', providerId: 'SM123' });
  expect(calls).toHaveLength(1);
  expect(calls[0].to).toBe('+15005550006');
  expect(calls[0].body).toContain('Sensor 1');
  expect(calls[0].body).toContain('34.2');
});

it('sends an SMS for a valid LOW event', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify({ ...base, transition: 'LOW' }, { sender, seen: new Set() });
  expect(out.code).toBe(200);
  expect(calls).toHaveLength(1);
});

it('rejects a NORMAL (recovery) transition without calling the sender', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify({ ...base, transition: 'NORMAL' }, { sender, seen: new Set() });
  expect(out.code).toBe(400);
  expect(calls).toHaveLength(0);
});

it('rejects a non-E.164 destination', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify({ ...base, destination: '5551234' }, { sender, seen: new Set() });
  expect(out.code).toBe(400);
  expect(calls).toHaveLength(0);
});

it('rejects a malformed event (empty message)', async () => {
  const { sender } = spySender();
  const out = await handleNotify({ ...base, message: '' }, { sender, seen: new Set() });
  expect(out.code).toBe(400);
});

it('skips a duplicate event id and does not re-send', async () => {
  const { sender, calls } = spySender();
  const seen = new Set<string>();
  await handleNotify(base, { sender, seen });
  const out = await handleNotify(base, { sender, seen });
  expect(out.code).toBe(200);
  expect(out.payload).toMatchObject({ status: 'skipped', reason: 'duplicate' });
  expect(calls).toHaveLength(1);
});

it('returns 502 when the provider throws', async () => {
  const { sender } = spySender({ throws: true });
  const out = await handleNotify(base, { sender, seen: new Set() });
  expect(out.code).toBe(502);
  expect(out.payload).toMatchObject({ status: 'failed' });
});
