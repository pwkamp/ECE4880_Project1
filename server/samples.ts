const STATUSES = ['VALID', 'DISCONNECTED', 'NOT_RETRIEVED', 'MISSING'] as const;
export type SampleStatus = (typeof STATUSES)[number];

export interface SampleRow {
  observed_at_utc: string;
  sensor1_c: number | null;
  sensor1_status: SampleStatus;
  sensor2_c: number | null;
  sensor2_status: SampleStatus;
}

export interface SampleStore {
  latest(): Promise<SampleRow | null>;
  history(seconds: number): Promise<SampleRow[]>;
  close?(): Promise<void>;
}

function asStatus(value: unknown): SampleStatus {
  const status = String(value);
  if (!(STATUSES as readonly string[]).includes(status)) {
    throw new Error(`invalid sensor status "${status}"`);
  }
  return status as SampleStatus;
}

function asCelsius(value: unknown): number | null {
  if (value == null || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function asUtc(value: unknown): string {
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

/** Normalize one temperature_samples row from mysql2. */
export function parseSampleRow(raw: Record<string, unknown>): SampleRow {
  return {
    observed_at_utc: asUtc(raw.observed_at_utc),
    sensor1_c: asCelsius(raw.sensor1_c),
    sensor1_status: asStatus(raw.sensor1_status),
    sensor2_c: asCelsius(raw.sensor2_c),
    sensor2_status: asStatus(raw.sensor2_status),
  };
}

const SELECT_COLS =
  'observed_at_utc, sensor1_c, sensor1_status, sensor2_c, sensor2_status';

export async function createMysqlSampleStore(url: string): Promise<SampleStore> {
  const mysql = await import('mysql2/promise');
  const pool = mysql.createPool(url);
  return {
    async latest() {
      const [rows] = await pool.query(
        `SELECT ${SELECT_COLS} FROM temperature_samples ORDER BY observed_at_utc DESC LIMIT 1`,
      );
      const list = rows as Record<string, unknown>[];
      return list[0] ? parseSampleRow(list[0]) : null;
    },
    async history(seconds: number) {
      const window = Number.isFinite(seconds) ? Math.max(1, Math.min(seconds, 3600)) : 300;
      const [rows] = await pool.query(
        `SELECT ${SELECT_COLS} FROM temperature_samples
         WHERE observed_at_utc >= UTC_TIMESTAMP() - INTERVAL ? SECOND
         ORDER BY observed_at_utc ASC`,
        [window],
      );
      return (rows as Record<string, unknown>[]).map(parseSampleRow);
    },
    async close() {
      await pool.end();
    },
  };
}
