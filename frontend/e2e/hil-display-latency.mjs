import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL = process.env.VERIFICATION_FRONTEND_URL ?? 'http://127.0.0.1:5173';
const evidenceDir = process.env.VERIFICATION_EVIDENCE_DIR;
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

try {
  // The live UI polls continuously, so networkidle may never occur even when
  // the page is fully usable. DOM readiness plus an asserted heading is the
  // deterministic readiness boundary.
  await page.goto(baseURL, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { level: 1, name: 'Networked Thermometer' }).waitFor();
  if (evidenceDir) {
    await fs.mkdir(evidenceDir, { recursive: true });
    await page.screenshot({ path: path.join(evidenceDir, 'live-display-controls-before.png'), fullPage: true });
  }
  for (let trial = 1; trial <= 20; trial += 1) {
    const sensor = trial % 2 === 1 ? 1 : 2;
    const control = page.locator(`input[type="checkbox"][aria-label="Sensor ${sensor} display"]`);
    await control.waitFor({ state: 'visible' });
    const desired = !(await control.isChecked());
    const actionWallNs = BigInt(Date.now()) * 1_000_000n;
    process.stdout.write(`${JSON.stringify({ type: 'action', trial, sensor, enabled: desired, action_wall_ns: actionWallNs.toString() })}\n`);
    await control.click();
    if (desired) await control.waitFor({ state: 'attached' });
    await page.waitForFunction(
      ({ label, checked }) => document.querySelector(`input[aria-label="${label}"]`)?.checked === checked,
      { label: `Sensor ${sensor} display`, checked: desired },
    );
    await page.waitForTimeout(1100);
  }
  if (evidenceDir) {
    await fs.mkdir(evidenceDir, { recursive: true });
    await page.screenshot({ path: path.join(evidenceDir, 'live-display-controls.png'), fullPage: true });
  }
} catch (error) {
  if (evidenceDir) {
    await fs.mkdir(evidenceDir, { recursive: true });
    await page.screenshot({ path: path.join(evidenceDir, 'live-display-controls-failure.png'), fullPage: true });
  }
  throw error;
} finally {
  await browser.close();
}
