import { z } from 'zod';

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const PersistedRecipientSchema = z
  .object({
    id: z.string().min(1).max(255),
    destination: z.string().trim().toLowerCase().regex(EMAIL),
    enabled: z.boolean(),
    minC: z.number().min(-55).max(125),
    maxC: z.number().min(-55).max(125),
    minMessage: z.string().min(1).max(255),
    maxMessage: z.string().min(1).max(255),
  })
  .refine((value) => value.minC < value.maxC, {
    message: 'minC must be below maxC',
    path: ['minC'],
  });

export const PersistedAlertConfigSchema = z
  .object({
    enabled: z.boolean(),
    recipients: z.array(PersistedRecipientSchema).max(25),
  })
  .superRefine((value, context) => {
    const seen = new Set<string>();
    value.recipients.forEach((recipient, index) => {
      if (seen.has(recipient.destination)) {
        context.addIssue({
          code: 'custom',
          message: 'recipient email addresses must be unique',
          path: ['recipients', index, 'destination'],
        });
      }
      seen.add(recipient.destination);
    });
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
  await pool.query(
    'ALTER TABLE alert_recipients ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE',
  );
  await pool.query(
    'ALTER TABLE alert_rules ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE',
  );
  await pool.query(
    `CREATE TABLE IF NOT EXISTS alert_settings (
       id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
       enabled BOOLEAN NOT NULL DEFAULT TRUE,
       updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
       CHECK (id = 1)
     )`,
  );
  await pool.query(
    'INSERT INTO alert_settings (id, enabled) VALUES (1, TRUE) ON DUPLICATE KEY UPDATE id=id',
  );
  return {
    async load() {
      const [settingRowsResult] = await pool.query(
        'SELECT enabled FROM alert_settings WHERE id=1',
      );
      const [rowsResult] = await pool.query(
        `SELECT recipient.id AS recipient_id, recipient.address,
                recipient.enabled AS recipient_enabled,
                rule.min_threshold, rule.max_threshold,
                rule.high_temp_message, rule.low_temp_message,
                rule.enabled AS rule_enabled, rule.monitored_series
           FROM alert_recipients AS recipient
           JOIN alert_rule_recipients AS link ON link.alert_recipient_id = recipient.id
           JOIN alert_rules AS rule ON rule.id = link.alert_rule_id
          WHERE recipient.type='EMAIL'
          ORDER BY recipient.id ASC, rule.id ASC`,
      );
      const rows = rowsResult as Record<string, unknown>[];
      const settingRows = settingRowsResult as Record<string, unknown>[];
      const byRecipient = new Map<string, PersistedAlertConfig['recipients'][number]>();
      for (const row of rows) {
        const id = `recipient-${String(row.recipient_id)}`;
        if (!byRecipient.has(id)) {
          byRecipient.set(id, {
            id,
            destination: String(row.address),
            enabled: Boolean(row.recipient_enabled),
            minC: Number(row.min_threshold),
            maxC: Number(row.max_threshold),
            minMessage: String(row.low_temp_message),
            maxMessage: String(row.high_temp_message),
          });
        }
      }
      return PersistedAlertConfigSchema.parse({
        enabled: Boolean(settingRows[0]?.enabled ?? true),
        recipients: [...byRecipient.values()],
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
        await connection.execute(
          'INSERT INTO alert_settings (id,enabled) VALUES (1,?) ON DUPLICATE KEY UPDATE enabled=VALUES(enabled)',
          [valid.enabled],
        );
        for (const recipient of valid.recipients) {
          const [recipientResult] = await connection.execute(
            `INSERT INTO alert_recipients (type,address,enabled)
             VALUES ('EMAIL',?,?)`,
            [recipient.destination, recipient.enabled],
          );
          const recipientId = (recipientResult as { insertId: number }).insertId;
          for (const source of ['SENSOR1', 'SENSOR2'] as const) {
            const [ruleResult] = await connection.execute(
              `INSERT INTO alert_rules
                 (min_threshold,max_threshold,high_temp_message,low_temp_message,monitored_series,enabled)
               VALUES (?,?,?,?,?,?)`,
              [
                recipient.minC,
                recipient.maxC,
                recipient.maxMessage,
                recipient.minMessage,
                source,
                recipient.enabled,
              ],
            );
            await connection.execute(
              'INSERT INTO alert_rule_recipients (alert_rule_id,alert_recipient_id) VALUES (?,?)',
              [(ruleResult as { insertId: number }).insertId, recipientId],
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
