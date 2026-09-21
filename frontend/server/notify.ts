import { z } from 'zod';
import type { SmsSender } from './sms/types.ts';

export const AlertEventSchema = z.object({
  id: z.string().min(1),
  timestamp: z.number(),
  recipientId: z.string(),
  ruleId: z.string(),
  source: z.enum(['SENSOR_1', 'SENSOR_2', 'AVERAGE']),
  transition: z.enum(['NORMAL', 'HIGH', 'LOW']),
  destination: z.string(),
  message: z.string().min(1),
  celsius: z.number(),
});

export type AlertEventInput = z.infer<typeof AlertEventSchema>;

export interface NotifyDeps {
  sender: SmsSender;
  /** Event ids already delivered. The caller owns and size-caps this. */
  seen: Set<string>;
}

export interface NotifyOutcome {
  code: 200 | 400 | 502;
  payload: Record<string, unknown>;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Trim and lowercase an email, or null if it isn't a usable address. */
export function normalizeDestination(raw: string): string | null {
  const email = raw.trim().toLowerCase();
  return EMAIL.test(email) ? email : null;
}

const SOURCE_LABEL: Record<AlertEventInput['source'], string> = {
  SENSOR_1: 'Sensor 1',
  SENSOR_2: 'Sensor 2',
  AVERAGE: 'Sensor average',
};

export interface ComposedEmail {
  subject: string;
  text: string;
  html: string;
}

/** Subject + plain text + HTML for a HIGH/LOW threshold crossing. */
export function composeAlertEmail(event: AlertEventInput): ComposedEmail {
  const sensor = SOURCE_LABEL[event.source];
  const reading = `${event.celsius.toFixed(1)}°C`;
  const kind = event.transition === 'HIGH' ? 'HIGH' : 'LOW';
  const when = new Date(event.timestamp).toUTCString();
  const subject = `${kind} temperature alert - ${sensor} at ${reading}`;
  const text = [
    'Networked Thermometer alert',
    '',
    `Status:  ${kind}`,
    `Sensor:  ${sensor}`,
    `Reading: ${reading}`,
    `Time:    ${when}`,
    '',
    event.message,
    '',
    'This message was sent by the networked thermometer computer console.',
  ].join('\n');
  const accent = event.transition === 'HIGH' ? '#c62828' : '#1565c0';
  const html = `<div style="font-family:Segoe UI,Helvetica,Arial,sans-serif;max-width:520px;color:#1a1a1a;line-height:1.45">
  <h1 style="font-size:18px;margin:0 0 4px">Networked Thermometer</h1>
  <p style="margin:0 0 16px;font-size:14px;color:#5a5a5a">Threshold alert from the computer console</p>
  <p style="margin:0 0 16px;font-size:16px"><strong style="color:${accent}">${kind}</strong> on ${sensor}</p>
  <table style="border-collapse:collapse;width:100%;font-size:14px">
    <tr><td style="padding:6px 0;color:#5a5a5a;width:96px">Sensor</td><td>${escapeHtml(sensor)}</td></tr>
    <tr><td style="padding:6px 0;color:#5a5a5a">Reading</td><td><strong>${escapeHtml(reading)}</strong></td></tr>
    <tr><td style="padding:6px 0;color:#5a5a5a">Status</td><td>${kind}</td></tr>
    <tr><td style="padding:6px 0;color:#5a5a5a">Time (UTC)</td><td>${escapeHtml(when)}</td></tr>
  </table>
  <p style="margin:16px 0 0">${escapeHtml(event.message)}</p>
  <p style="margin:20px 0 0;font-size:12px;color:#5a5a5a">Sent automatically when a sensor crossed the configured min/max threshold.</p>
</div>`;
  return { subject, text, html };
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

export async function handleNotify(rawBody: unknown, deps: NotifyDeps): Promise<NotifyOutcome> {
  const parsed = AlertEventSchema.safeParse(rawBody);
  if (!parsed.success) {
    return { code: 400, payload: { status: 'failed', error: 'invalid event', detail: parsed.error.issues } };
  }
  const event = parsed.data;

  if (event.transition !== 'HIGH' && event.transition !== 'LOW') {
    return { code: 400, payload: { status: 'failed', error: 'not a deliverable transition' } };
  }
  const destination = normalizeDestination(event.destination);
  if (!destination) {
    return { code: 400, payload: { status: 'failed', error: 'destination is not a valid email' } };
  }
  if (deps.seen.has(event.id)) {
    return { code: 200, payload: { status: 'skipped', reason: 'duplicate' } };
  }

  try {
    const email = composeAlertEmail(event);
    const result = await deps.sender.send({
      to: destination,
      body: email.text,
      subject: email.subject,
      html: email.html,
    });
    deps.seen.add(event.id);
    return { code: 200, payload: { status: result.status, providerId: result.providerId } };
  } catch (err) {
    return { code: 502, payload: { status: 'failed', reason: err instanceof Error ? err.message : String(err) } };
  }
}
