import type { AlertEvent } from './alertEngine';

export interface DeliveryResult {
  ok: boolean;
  status: string;
  reason?: string;
}

const TOKEN: string | undefined = import.meta.env.VITE_ALERT_API_TOKEN;

/** POST one alert event to the delivery service. Never throws. */
export async function notifyAlert(event: AlertEvent): Promise<DeliveryResult> {
  try {
    const res = await fetch('/api/notify', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        ...(TOKEN ? { authorization: `Bearer ${TOKEN}` } : {}),
      },
      body: JSON.stringify(event),
    });
    const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (res.ok) {
      return { ok: true, status: String(payload.status ?? 'sent') };
    }
    const reason = payload.reason ?? payload.error;
    return {
      ok: false,
      status: String(payload.status ?? 'error'),
      reason: reason === undefined ? undefined : String(reason),
    };
  } catch {
    return { ok: false, status: 'unreachable' };
  }
}
