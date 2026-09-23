/** UI-facing, MySQL-persisted email alert configuration. */

export interface AlertRecipientConfig {
  id: string;
  destination: string;
  enabled: boolean;
  /** Thresholds are stored in Celsius regardless of the display unit. */
  maxC: number;
  minC: number;
  maxMessage: string;
  minMessage: string;
}

export interface AlertConfig {
  enabled: boolean;
  recipients: AlertRecipientConfig[];
}

export const DEFAULT_ALERT_CONFIG: AlertConfig = {
  enabled: true,
  recipients: [],
};

export function defaultRecipient(destination: string, id = destination): AlertRecipientConfig {
  return {
    id,
    destination,
    enabled: true,
    maxC: 30,
    minC: 15,
    maxMessage: 'Temperature high: sensor above the configured maximum.',
    minMessage: 'Temperature low: sensor below the configured minimum.',
  };
}
