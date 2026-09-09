import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { loadServerEnv } from './loadEnv.ts';

it('returns false when the env file is missing', () => {
  expect(loadServerEnv(join(tmpdir(), 'no-such-ece4880.env'))).toBe(false);
});

it('loads KEY=value pairs into process.env', () => {
  const dir = mkdtempSync(join(tmpdir(), 'sms-env-'));
  const file = join(dir, '.env');
  writeFileSync(file, 'ECE4880_ENV_PROBE=from-file\n');
  const previous = process.env.ECE4880_ENV_PROBE;
  delete process.env.ECE4880_ENV_PROBE;
  try {
    expect(loadServerEnv(file)).toBe(true);
    expect(process.env.ECE4880_ENV_PROBE).toBe('from-file');
  } finally {
    if (previous === undefined) delete process.env.ECE4880_ENV_PROBE;
    else process.env.ECE4880_ENV_PROBE = previous;
    rmSync(dir, { recursive: true, force: true });
  }
});
