import { expect, it } from 'vitest';
import { loadConfig } from './config.ts';

it('defaults to console mode when nothing is set', () => {
  const c = loadConfig({} as NodeJS.ProcessEnv);
  expect(c.mode).toBe('console');
  expect(c.port).toBe(8787);
  expect(c.apiToken).toBeNull();
  expect(c.smtp).toBeNull();
});

it('rejects an unknown EMAIL_MODE', () => {
  expect(() => loadConfig({ EMAIL_MODE: 'carrier-pigeon' } as NodeJS.ProcessEnv)).toThrow(/EMAIL_MODE/);
});

it('throws when live mode is missing SMTP vars', () => {
  expect(() => loadConfig({ SMS_MODE: 'live' } as NodeJS.ProcessEnv)).toThrow(/SMTP_USER/);
});

it('accepts a complete live Gmail config', () => {
  const c = loadConfig({
    EMAIL_MODE: 'live',
    SMTP_USER: 'alerts@gmail.com',
    SMTP_PASS: 'app-password',
  } as NodeJS.ProcessEnv);
  expect(c.mode).toBe('live');
  expect(c.smtp).toEqual({
    host: 'smtp.gmail.com',
    port: 465,
    secure: true,
    user: 'alerts@gmail.com',
    pass: 'app-password',
    fromEmail: 'alerts@gmail.com',
  });
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
