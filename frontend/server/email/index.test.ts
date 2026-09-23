import { expect, it, vi } from 'vitest';
import { createEmailSender } from './index.ts';

it('returns a console sender in console mode', async () => {
  const spy = vi.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const sender = createEmailSender({ mode: 'console', port: 8787, apiToken: null, smtp: null, mysqlUrl: null });
    await expect(sender.send({ to: 'you@example.com', body: 'x' })).resolves.toEqual({ status: 'logged' });
  } finally {
    spy.mockRestore();
  }
});

it('returns an SMTP-backed sender when live config is present', () => {
  const sender = createEmailSender({
    mode: 'live',
    port: 8787,
    apiToken: null,
    smtp: {
      host: 'smtp.gmail.com',
      port: 465,
      secure: true,
      user: 'alerts@gmail.com',
      pass: 'app-password',
      fromEmail: 'alerts@gmail.com',
    },
    mysqlUrl: null,
  });
  expect(typeof sender.send).toBe('function');
});
