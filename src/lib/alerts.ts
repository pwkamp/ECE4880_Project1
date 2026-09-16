/**
 * UI-facing alert configuration.
 *
 * The threshold + message + destination fields the "Threshold alerts" panel
 * edits. `App.tsx` adapts one `AlertConfig` into the `AlertRule` /
 * `AlertRecipient` inputs of the alert engine (see `src/lib/alertEngine.ts`),
 * which owns the actual NORMAL/HIGH/LOW state machine.
 */
export interface AlertConfig {
  enabled: boolean;
  /** Thresholds are stored in Celsius regardless of the display unit. */
  maxC: number;
  minC: number;
  maxMessage: string;
  minMessage: string;
  /** Phone number in E.164 format (e.g. +15555550123). Used as the SMS destination. */
  destination: string;
}

export const DEFAULT_ALERT_CONFIG: AlertConfig = {
  enabled: true,
  maxC: 30,
  minC: 15,
  maxMessage: 'Temperature high: sensor above the configured maximum.',
  minMessage: 'Temperature low: sensor below the configured minimum.',
  destination: '+15555550123',
};
