import { z } from 'zod';

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const PersistedAlertConfigSchema = z
  .object({
    enabled: z.boolean(),
    minC: z.number().min(-55).max(125),
    maxC: z.number().min(-55).max(125),
    minMessage: z.string().min(1).max(255),
    maxMessage: z.string().min(1).max(255),
    destinations: z.array(z.string().trim().toLowerCase().regex(EMAIL)).max(25),
  })
  .refine((value) => value.minC < value.maxC, {
    message: 'minC must be below maxC',
    path: ['minC'],
  });

export type PersistedAlertConfig = z.infer<typeof PersistedAlertConfigSchema>;

export interface AlertConfigStore {
  load(): Promise<PersistedAlertConfig | null>;
  save(config: PersistedAlertConfig): Promise<void>;
  close?(): Promise<void>;
}

export async function createMysqlAlertConfigStore(url: string): Promise<AlertConfigStore> {
  const mysql = await import('mysql2/promise');
  const pool = mysql.createPool(url);
  // Existing developer volumes may predate alert enable/disable support.
  // These idempotent, additive migrations keep those volumes usable without
  // deleting captured temperature evidence. Fresh databases still receive the
  // complete definition from backend/database/schema.sql.
  await pool.query(
    'ALTER TABLE alert_recipients ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE',
  );
  await pool.query(
    'ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE',
  );
  return {
    async load() {
      const [ruleRows] = await pool.query(
        `SELECT enabled, min_threshold, max_threshold, high_temp_message, low_temp_message
           FROM alert_rules ORDER BY id ASC LIMIT 1`,
      );
      const rules = ruleRows as Record<string, unknown>[];
      if (!rules[0]) return null;
      const [recipientRows] = await pool.query(
        `SELECT address FROM alert_recipients
          WHERE type='EMAIL' AND enabled=TRUE ORDER BY id ASC`,
      );
      const rule = rules[0];
      return PersistedAlertConfigSchema.parse({
        enabled: Boolean(rule.enabled),
        minC: Number(rule.min_threshold),
        maxC: Number(rule.max_threshold),
        minMessage: String(rule.low_temp_message),
        maxMessage: String(rule.high_temp_message),
        destinations: (recipientRows as Record<string, unknown>[]).map((row) => String(row.address)),
      });
    },
    async save(config) {
      const valid = PersistedAlertConfigSchema.parse(config);
      const connection = await pool.getConnection();
      try {
        await connection.beginTransaction();
        await connection.query('DELETE FROM alert_rule_recipients');
        await connection.query('DELETE FROM alert_rules');
        await connection.query('DELETE FROM alert_recipients');
        const ruleIds: number[] = [];
        for (const source of ['SENSOR1', 'SENSOR2'] as const) {
          const [ruleResult] = await connection.execute(
            `INSERT INTO alert_rules
               (min_threshold,max_threshold,high_temp_message,low_temp_message,monitored_series,enabled)
             VALUES (?,?,?,?,?,?)`,
            [valid.minC, valid.maxC, valid.maxMessage, valid.minMessage, source, valid.enabled],
          );
          ruleIds.push((ruleResult as { insertId: number }).insertId);
        }
        for (const destination of [...new Set(valid.destinations)]) {
          const [recipientResult] = await connection.execute(
            `INSERT INTO alert_recipients (type,address,enabled) VALUES ('EMAIL',?,TRUE)`,
            [destination],
          );
          const recipientId = (recipientResult as { insertId: number }).insertId;
          for (const ruleId of ruleIds) {
            await connection.execute(
              'INSERT INTO alert_rule_recipients (alert_rule_id,alert_recipient_id) VALUES (?,?)',
              [ruleId, recipientId],
            );
          }
        }
        await connection.commit();
      } catch (error) {
        await connection.rollback();
        throw error;
      } finally {
        connection.release();
      }
    },
    async close() {
      await pool.end();
    },
  };
}
