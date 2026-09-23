import { expect, test } from '@playwright/test';
import { installScenario } from '../fixtures/scenario';

test('disconnected sensor does not retain a numeric current value', async ({ page }, testInfo) => {
  await installScenario(page, 'sensor_1_disconnected');
  await page.goto('/');
  await expect(page.locator('.readout-sensor-1 .readout-message')).toHaveText('unplugged sensor');
  await page.screenshot({ path: testInfo.outputPath('actual-gui-sensor-disconnected.png'), fullPage: true });
});

test('unavailable box shows the required exact text', async ({ page }, testInfo) => {
  await installScenario(page, 'box_off');
  await page.goto('/');
  await expect(page.locator('.readout-sensor-1 .readout-message')).toHaveText('no data available');
  await expect(page.locator('.readout-sensor-2 .readout-message')).toHaveText('no data available');
  await page.screenshot({ path: testInfo.outputPath('actual-gui-box-off.png'), fullPage: true });
});
