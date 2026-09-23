import { expect, it, vi } from 'vitest';
import { createConsoleEmailSender } from './consoleSender.ts';

it('logs the message and reports "logged"', async () => {
  const spy = vi.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const result = await createConsoleEmailSender().send({ to: 'you@example.com', body: 'sensor 1 hot' });
    expect(result).toEqual({ status: 'logged' });
    expect(spy).toHaveBeenCalledOnce();
    expect(String(spy.mock.calls[0][0])).toBe(
      'Email sent to you@example.com: "sensor 1 hot"',
    );
  } finally {
    spy.mockRestore();
  }
});
