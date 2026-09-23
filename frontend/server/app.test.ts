import request from 'supertest';
import { expect, it } from 'vitest';
import { createApp } from './app.ts';
import type { Config } from './config.ts';
import type { AlertConfigStore, PersistedAlertConfig } from './alertConfig.ts';
import type { EmailSender } from './email/types.ts';

const consoleConfig: Config = {
  mode: 'console',
  port: 8787,
  apiToken: null,
  smtp: null,
  mysqlUrl: null,
};
const okSender: EmailSender = { async send() { return { status: 'logged' }; } };

const validEvent = {
  id: 'e1',
  timestamp: 1000,
  recipientId: 'primary',
  ruleId: 'sensor-1',
  source: 'SENSOR_1',
  transition: 'HIGH',
  destination: 'you@example.com',
  message: 'Temperature high.',
  celsius: 40,
};

it('POST /api/notify delivers a valid event', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const res = await request(app).post('/api/notify').send(validEvent);
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('logged');
});

it('POST /api/notify returns 400 for a bad destination', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const res = await request(app).post('/api/notify').send({ ...validEvent, destination: 'nope' });
  expect(res.status).toBe(400);
});

it('GET /api/health reports the mode', () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  return request(app)
    .get('/api/health')
    .then((res) => {
      expect(res.status).toBe(200);
      expect(res.body).toEqual({ status: 'ok', mode: 'console', verification_contract: 2 });
    });
});

it('GET /api/samples reports the DB reader as unconfigured by default', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const latest = await request(app).get('/api/samples/latest');
  const history = await request(app).get('/api/samples?seconds=300');
  expect(latest.body).toEqual({ configured: false, row: null });
  expect(history.body).toEqual({ configured: false, rows: [] });
});

it('persists and reloads validated email-only alert configuration', async () => {
  let saved: PersistedAlertConfig | null = null;
  const store: AlertConfigStore = {
    async load() { return saved; },
    async save(config) { saved = config; },
  };
  const app = createApp({ config: consoleConfig, sender: okSender, alertConfig: store });
  const config: PersistedAlertConfig = {
    enabled: true,
    recipients: [
      { id: 'one', destination: 'one@example.com', enabled: true, minC: 10, maxC: 30, minMessage: 'cold one', maxMessage: 'hot one' },
      { id: 'two', destination: 'two@example.com', enabled: false, minC: 5, maxC: 35, minMessage: 'cold two', maxMessage: 'hot two' },
    ],
  };
  const update = await request(app).put('/api/alert-config').send(config);
  expect(update.status).toBe(200);
  const reload = await request(app).get('/api/alert-config');
  expect(reload.body.config).toEqual(config);
});

it('rejects invalid alert thresholds and non-email destinations', async () => {
  const store: AlertConfigStore = { async load() { return null; }, async save() {} };
  const app = createApp({ config: consoleConfig, sender: okSender, alertConfig: store });
  const invalid = await request(app).put('/api/alert-config').send({
    enabled: true,
    recipients: [{
      id: 'bad', destination: 'not-an-email', enabled: true,
      minC: 30, maxC: 10, minMessage: 'low', maxMessage: 'high',
    }],
  });
  expect(invalid.status).toBe(400);
});

it('enforces the bearer token when one is configured', async () => {
  const app = createApp({ config: { ...consoleConfig, apiToken: 'sekret' }, sender: okSender });
  const noAuth = await request(app).post('/api/notify').send(validEvent);
  expect(noAuth.status).toBe(401);
  const withAuth = await request(app)
    .post('/api/notify')
    .set('authorization', 'Bearer sekret')
    .send(validEvent);
  expect(withAuth.status).toBe(200);
});
