export type SmsMode = 'console' | 'test' | 'live';

export interface TwilioConfig {
  accountSid: string;
  authToken: string;
  fromNumber: string;
}

export interface Config {
  mode: SmsMode;
  port: number;
  apiToken: string | null;
  twilio: TwilioConfig | null;
}

const MODES: readonly SmsMode[] = ['console', 'test', 'live'];

export function loadConfig(env: NodeJS.ProcessEnv): Config {
  const rawMode = env.SMS_MODE ?? 'console';
  if (!MODES.includes(rawMode as SmsMode)) {
    throw new Error(`SMS_MODE must be one of ${MODES.join(', ')} (got "${rawMode}")`);
  }
  const mode = rawMode as SmsMode;

  const port = env.PORT ? Number(env.PORT) : 8787;
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`PORT must be a positive integer (got "${env.PORT}")`);
  }

  const apiToken = env.ALERT_API_TOKEN && env.ALERT_API_TOKEN.length > 0 ? env.ALERT_API_TOKEN : null;

  let twilio: TwilioConfig | null = null;
  if (mode === 'test' || mode === 'live') {
    const accountSid = env.TWILIO_ACCOUNT_SID ?? '';
    const authToken = env.TWILIO_AUTH_TOKEN ?? '';
    const fromNumber = env.TWILIO_FROM_NUMBER ?? '';
    const missing = ([
      ['TWILIO_ACCOUNT_SID', accountSid],
      ['TWILIO_AUTH_TOKEN', authToken],
      ['TWILIO_FROM_NUMBER', fromNumber],
    ] as const)
      .filter(([, value]) => value.length === 0)
      .map(([name]) => name);
    if (missing.length > 0) {
      throw new Error(`SMS_MODE=${mode} requires: ${missing.join(', ')}`);
    }
    twilio = { accountSid, authToken, fromNumber };
  }

  return { mode, port, apiToken, twilio };
}
