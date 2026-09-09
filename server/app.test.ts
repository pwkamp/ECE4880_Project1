import request from 'supertest';
import { expect, it } from 'vitest';
import { createApp } from './app.ts';
import type { Config } from './config.ts';
import type { SmsSender } from './sms/types.ts';

const consoleConfig: Config = {
  mode: 'console',
  port: 8787,
  apiToken: null,
  twilio: null,
  mysqlUrl: null,
};
const okSender: SmsSender = { async send() { return { status: 'logged' }; } };

const validEvent = {
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
      expect(res.body).toEqual({ status: 'ok', mode: 'console' });
    });
});

it('GET /api/samples reports the DB reader as unconfigured by default', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const latest = await request(app).get('/api/samples/latest');
  const history = await request(app).get('/api/samples?seconds=300');
  expect(latest.body).toEqual({ configured: false, row: null });
  expect(history.body).toEqual({ configured: false, rows: [] });
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
