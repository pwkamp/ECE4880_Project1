export type EmailMode = 'console' | 'test' | 'live';

export interface SmtpConfig {
  host: string;
  port: number;
  secure: boolean;
  user: string;
  pass: string;
  fromEmail: string;
}

export interface Config {
  mode: EmailMode;
  port: number;
  apiToken: string | null;
  smtp: SmtpConfig | null;
  /** mysql:// URL for temperature_samples. Null means the DB reader is off. */
  mysqlUrl: string | null;
}

const MODES: readonly EmailMode[] = ['console', 'test', 'live'];

export function loadConfig(env: NodeJS.ProcessEnv): Config {
  const rawMode = env.EMAIL_MODE ?? 'console';
  if (!MODES.includes(rawMode as EmailMode)) {
    throw new Error(`EMAIL_MODE must be one of ${MODES.join(', ')} (got "${rawMode}")`);
  }
  const mode = rawMode as EmailMode;

  const port = env.PORT ? Number(env.PORT) : 8787;
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`PORT must be a positive integer (got "${env.PORT}")`);
  }

  const apiToken = env.ALERT_API_TOKEN && env.ALERT_API_TOKEN.length > 0 ? env.ALERT_API_TOKEN : null;

  let smtp: SmtpConfig | null = null;
  if (mode === 'test' || mode === 'live') {
    const user = env.SMTP_USER ?? '';
    const pass = env.SMTP_PASS ?? '';
    const missing = ([
      ['SMTP_USER', user],
      ['SMTP_PASS', pass],
    ] as const)
      .filter(([, value]) => value.length === 0)
      .map(([name]) => name);
    if (missing.length > 0) {
      throw new Error(`EMAIL_MODE=${mode} requires: ${missing.join(', ')}`);
    }
    const smtpPort = env.SMTP_PORT ? Number(env.SMTP_PORT) : 465;
    if (!Number.isInteger(smtpPort) || smtpPort <= 0) {
      throw new Error(`SMTP_PORT must be a positive integer (got "${env.SMTP_PORT}")`);
    }
    smtp = {
      host: env.SMTP_HOST?.trim() || 'smtp.gmail.com',
      port: smtpPort,
      secure: env.SMTP_SECURE ? env.SMTP_SECURE === 'true' : smtpPort === 465,
      user,
      pass,
      fromEmail: env.SMTP_FROM?.trim() || user,
    };
  }

  return { mode, port, apiToken, smtp, mysqlUrl: env.MYSQL_URL || null };
}
