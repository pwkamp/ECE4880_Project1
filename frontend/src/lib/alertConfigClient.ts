import type { AlertConfig } from './alerts';

export async function loadAlertConfig(): Promise<AlertConfig | null> {
  const response = await fetch('/api/alert-config');
  if (!response.ok) throw new Error(`alert configuration load failed (${response.status})`);
  const body = (await response.json()) as { config?: AlertConfig | null };
  return body.config ?? null;
}

export async function saveAlertConfig(config: AlertConfig): Promise<void> {
  const response = await fetch('/api/alert-config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) throw new Error(`alert configuration save failed (${response.status})`);
}

