import { beforeEach, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  const execute = vi.fn();
  const connection = {
    beginTransaction: vi.fn(),
    query: vi.fn(),
    execute,
    commit: vi.fn(),
    rollback: vi.fn(),
    release: vi.fn(),
  };
  const pool = {
    query: vi.fn(),
    getConnection: vi.fn(async () => connection),
    end: vi.fn(),
  };
  return { connection, execute, pool, createPool: vi.fn(() => pool) };
});

vi.mock('mysql2/promise', () => ({ createPool: mocks.createPool }));

import { createMysqlAlertConfigStore } from './alertConfig.ts';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.pool.query.mockResolvedValue([[], []]);
  mocks.connection.query.mockResolvedValue([[], []]);
  let insertId = 0;
  mocks.execute.mockImplementation(async () => [{ insertId: ++insertId }, []]);
});

it('persists independent enabled state, thresholds, and messages for each recipient', async () => {
  const store = await createMysqlAlertConfigStore('mysql://test');
  await store.save({
    enabled: true,
    recipients: [
      { id: 'one', destination: 'one@example.com', enabled: true, minC: 1, maxC: 21, minMessage: 'one low', maxMessage: 'one high' },
      { id: 'two', destination: 'two@example.com', enabled: false, minC: 2, maxC: 32, minMessage: 'two low', maxMessage: 'two high' },
    ],
  });

  const inserts = mocks.execute.mock.calls.filter(([sql]) => String(sql).includes('INSERT INTO alert_rules'));
  expect(inserts).toHaveLength(4);
  expect(inserts[0][1]).toEqual([1, 21, 'one high', 'one low', 'SENSOR1', true]);
  expect(inserts[2][1]).toEqual([2, 32, 'two high', 'two low', 'SENSOR1', false]);
  expect(mocks.connection.commit).toHaveBeenCalledOnce();
});

it('loads distinct persisted recipient configurations', async () => {
  mocks.pool.query
    .mockResolvedValueOnce([[], []])
    .mockResolvedValueOnce([[], []])
    .mockResolvedValueOnce([[], []])
    .mockResolvedValueOnce([[], []])
    .mockResolvedValueOnce([[{ enabled: 1 }], []])
    .mockResolvedValueOnce([[
      { recipient_id: 1, address: 'one@example.com', recipient_enabled: 1, min_threshold: 1, max_threshold: 21, low_temp_message: 'one low', high_temp_message: 'one high', rule_enabled: 1, monitored_series: 'SENSOR1' },
      { recipient_id: 1, address: 'one@example.com', recipient_enabled: 1, min_threshold: 1, max_threshold: 21, low_temp_message: 'one low', high_temp_message: 'one high', rule_enabled: 1, monitored_series: 'SENSOR2' },
      { recipient_id: 2, address: 'two@example.com', recipient_enabled: 0, min_threshold: 2, max_threshold: 32, low_temp_message: 'two low', high_temp_message: 'two high', rule_enabled: 0, monitored_series: 'SENSOR1' },
    ], []]);

  const store = await createMysqlAlertConfigStore('mysql://test');
  const loaded = await store.load();
  expect(loaded).toEqual({
    enabled: true,
    recipients: [
      { id: 'recipient-1', destination: 'one@example.com', enabled: true, minC: 1, maxC: 21, minMessage: 'one low', maxMessage: 'one high' },
      { id: 'recipient-2', destination: 'two@example.com', enabled: false, minC: 2, maxC: 32, minMessage: 'two low', maxMessage: 'two high' },
    ],
  });
});
