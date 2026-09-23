import { defineConfig } from '@playwright/test';
import path from 'node:path';

const verificationEvidence = process.env.VERIFICATION_EVIDENCE_DIR;

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  // Chromium instances previously exhausted Windows' ephemeral socket/buffer
  // resources when all four viewport projects hit Vite concurrently.  Serial
  // execution is deterministic and still exercises every supported viewport.
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['junit', { outputFile: verificationEvidence ? path.join(verificationEvidence, 'playwright-junit.xml') : '../test-results/playwright-junit.xml' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'on',
  },
  projects: [
    { name: 'desktop-1440', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    { name: 'laptop-1280', use: { browserName: 'chromium', viewport: { width: 1280, height: 720 } } },
    { name: 'mobile-390', use: { browserName: 'chromium', viewport: { width: 390, height: 844 } } },
    { name: 'mobile-430', use: { browserName: 'chromium', viewport: { width: 430, height: 932 } } },
  ],
  outputDir: verificationEvidence ? path.join(verificationEvidence, 'playwright') : '../test-results/playwright',
});
