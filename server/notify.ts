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

const E164 = /^\+[1-9]\d{1,14}$/;

const SOURCE_LABEL: Record<AlertEventInput['source'], string> = {
  SENSOR_1: 'Sensor 1',
  SENSOR_2: 'Sensor 2',
  AVERAGE: 'Sensor average',
};

function composeBody(event: AlertEventInput): string {
  const text = `${event.message} (${SOURCE_LABEL[event.source]} ${event.celsius.toFixed(1)}°C)`;
  return text.length > 320 ? `${text.slice(0, 317)}...` : text;
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
  if (!E164.test(event.destination)) {
    return { code: 400, payload: { status: 'failed', error: 'destination is not E.164' } };
  }
  if (deps.seen.has(event.id)) {
    return { code: 200, payload: { status: 'skipped', reason: 'duplicate' } };
  }

  try {
    const result = await deps.sender.send({ to: event.destination, body: composeBody(event) });
    deps.seen.add(event.id);
    return { code: 200, payload: { status: result.status, providerId: result.providerId } };
  } catch (err) {
    return { code: 502, payload: { status: 'failed', reason: err instanceof Error ? err.message : String(err) } };
  }
}
