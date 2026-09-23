import type { Page, Route } from '@playwright/test';

const now = new Date().toISOString();

export type ScenarioName = 'normal' | 'sensor_1_disconnected' | 'box_off';

function samples(name: ScenarioName) {
  const disconnected = name === 'sensor_1_disconnected';
  const off = name === 'box_off';
  return Array.from({ length: 301 }, (_, index) => ({
    observed_at_utc: new Date(Date.now() - (300 - index) * 1000).toISOString(),
    sensor1_c: disconnected || off ? null : 21.5 + (index % 5) / 10,
    sensor1_status: disconnected ? 'DISCONNECTED' : off ? 'MISSING' : 'VALID',
    sensor2_c: off ? null : 22.5,
    sensor2_status: off ? 'MISSING' : 'VALID',
    average_c: disconnected || off ? null : 22.0,
    average_valid: !disconnected && !off,
  }));
}

export async function installScenario(page: Page, name: ScenarioName) {
  const rows = samples(name);
  await page.route('**/api/**', async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/v1/ble/status') {
      await route.fulfill({ json: {
        phase: name === 'box_off' ? 'RECONNECTING' : 'CONNECTED',
        connected: name !== 'box_off', ready: name !== 'box_off', desired_connected: true,
        target: { name: 'Thermometer-Test', address: 'AA:BB:CC:DD:EE:FF' },
        last_error: null, displays: [{ sensor_id: 1, enabled: true }, { sensor_id: 2, enabled: true }],
      }});
      return;
    }
    if (url.pathname === '/api/samples/latest') {
      await route.fulfill({ json: { configured: true, row: rows.at(-1) } });
      return;
    }
    if (url.pathname === '/api/samples') {
      await route.fulfill({ json: { configured: true, rows } });
      return;
    }
    await route.fulfill({ status: 404, json: { detail: `scenario route missing: ${url.pathname}`, at: now } });
  });
}
