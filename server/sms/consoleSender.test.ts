import { expect, it, vi } from 'vitest';
import { createConsoleSmsSender } from './consoleSender.ts';

it('logs the message and reports "logged"', async () => {
  const spy = vi.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const result = await createConsoleSmsSender().send({ to: '+15005550006', body: 'sensor 1 hot' });
    expect(result).toEqual({ status: 'logged' });
    expect(spy).toHaveBeenCalledOnce();
    expect(String(spy.mock.calls[0][0])).toBe(
      'Text message sent to +15005550006: "sensor 1 hot"',
    );
  } finally {
    spy.mockRestore();
  }
});
