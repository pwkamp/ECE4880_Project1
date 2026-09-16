import { expect, it } from 'vitest';
import { loadConfig } from './config.ts';

it('defaults to console mode when nothing is set', () => {
  const c = loadConfig({} as NodeJS.ProcessEnv);
  expect(c.mode).toBe('console');
  expect(c.port).toBe(8787);
  expect(c.apiToken).toBeNull();
  expect(c.twilio).toBeNull();
});

it('rejects an unknown SMS_MODE', () => {
  expect(() => loadConfig({ SMS_MODE: 'carrier-pigeon' } as NodeJS.ProcessEnv)).toThrow(/SMS_MODE/);
});

it('throws when test mode is missing Twilio vars', () => {
  expect(() => loadConfig({ SMS_MODE: 'test' } as NodeJS.ProcessEnv)).toThrow(/TWILIO_ACCOUNT_SID/);
});

it('accepts a complete live config', () => {
  const c = loadConfig({
    SMS_MODE: 'live',
    TWILIO_ACCOUNT_SID: 'AC1',
    TWILIO_AUTH_TOKEN: 'tok',
    TWILIO_FROM_NUMBER: '+15005550006',
  } as NodeJS.ProcessEnv);
  expect(c.mode).toBe('live');
  expect(c.twilio).toEqual({ accountSid: 'AC1', authToken: 'tok', fromNumber: '+15005550006' });
});

it('reads PORT and ALERT_API_TOKEN overrides', () => {
  const c = loadConfig({ PORT: '9000', ALERT_API_TOKEN: 'sekret' } as NodeJS.ProcessEnv);
  expect(c.port).toBe(9000);
  expect(c.apiToken).toBe('sekret');
});

it('reads MYSQL_URL when provided', () => {
  const c = loadConfig({
    MYSQL_URL: 'mysql://user:pass@127.0.0.1:3306/thermometer',
  } as NodeJS.ProcessEnv);
  expect(c.mysqlUrl).toBe('mysql://user:pass@127.0.0.1:3306/thermometer');
});
