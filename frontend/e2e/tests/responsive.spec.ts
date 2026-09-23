import { expect, test } from '@playwright/test';
import { installScenario } from '../fixtures/scenario';

test.beforeEach(async ({ page }) => {
  await installScenario(page, 'normal');
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
});

test('required controls remain usable without horizontal overflow', async ({ page }, testInfo) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await expect(page.getByRole('button', { name: 'Scan' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Connect', exact: true })).toBeVisible();
  await expect(page.getByText('Sensor 1', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('Sensor 2', { exact: false }).first()).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('actual-gui-responsive.png'), fullPage: true });
});
