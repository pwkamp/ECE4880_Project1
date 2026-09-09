import { expect, it, vi } from 'vitest';
import { createSmsSender } from './index.ts';

it('returns a console sender in console mode', async () => {
  const spy = vi.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const sender = createSmsSender({ mode: 'console', port: 8787, apiToken: null, twilio: null, mysqlUrl: null });
    await expect(sender.send({ to: '+15005550006', body: 'x' })).resolves.toEqual({ status: 'logged' });
  } finally {
    spy.mockRestore();
  }
});

it('returns a Twilio-backed sender when live config is present', () => {
  const sender = createSmsSender({
    mode: 'live',
    port: 8787,
    apiToken: null,
    twilio: { accountSid: 'AC0000000000000000000000000000000000', authToken: 'tok', fromNumber: '+15005550006' },
    mysqlUrl: null,
  });
  // Constructing the client is offline; we only assert the shape.
  expect(typeof sender.send).toBe('function');
});
