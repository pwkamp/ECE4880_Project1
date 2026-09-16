import { expect, it } from 'vitest';
import { parseSampleRow } from './samples.ts';

it('coerces MySQL DECIMAL strings and timestamps into a sample row', () => {
  const row = parseSampleRow({
    observed_at_utc: '2026-09-09 16:00:00',
    sensor1_c: '21.50',
    sensor1_status: 'VALID',
    sensor2_c: null,
    sensor2_status: 'DISCONNECTED',
  });
  expect(row).toEqual({
    observed_at_utc: '2026-09-09 16:00:00',
    sensor1_c: 21.5,
    sensor1_status: 'VALID',
    sensor2_c: null,
    sensor2_status: 'DISCONNECTED',
  });
});
