import type { SensorId } from './types';
import type { BleCurrent, BleDevice, BleStatus, SampleRow } from './bleMap';

export interface BleApiClientOptions {
  fetchFn?: typeof fetch;
  bleBase?: string;
  samplesBase?: string;
}

interface SamplesPayload {
  configured?: boolean;
  row?: SampleRow | null;
  rows?: SampleRow[];
}

/**
 * Browser/HTTP client for the teammate FastAPI BLE connector (127.0.0.1:8000)
 * and this app's optional MySQL sample reader (`/api/samples`).
 */
export class BleApiClient {
  private readonly fetchFn: typeof fetch;
  private readonly bleBase: string;
  private readonly samplesBase: string;

  constructor(options: BleApiClientOptions = {}) {
    this.fetchFn = options.fetchFn ?? fetch.bind(globalThis);
    this.bleBase = options.bleBase ?? '/api/v1/ble';
    this.samplesBase = options.samplesBase ?? '/api/samples';
  }

  async scan(): Promise<BleDevice[]> {
    const payload = await this.requestJson<{ devices: BleDevice[] }>(
      `${this.bleBase}/scan`,
      { method: 'POST' },
    );
    return payload.devices ?? [];
  }

  async connect(address: string, passkey?: string): Promise<void> {
    const body: { address: string; passkey?: string } = { address };
    if (passkey) body.passkey = passkey;
    await this.requestJson(`${this.bleBase}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  async disconnect(): Promise<void> {
    await this.requestJson(`${this.bleBase}/disconnect`, { method: 'POST' });
  }

  async reconnect(): Promise<void> {
    await this.requestJson(`${this.bleBase}/reconnect`, { method: 'POST' });
  }

  async getStatus(): Promise<BleStatus> {
    return this.requestJson<BleStatus>(`${this.bleBase}/status`);
  }

  async getCurrent(): Promise<BleCurrent> {
    return this.requestJson<BleCurrent>(`${this.bleBase}/current`);
  }

  async setDisplay(sensorId: SensorId, enabled: boolean): Promise<void> {
    await this.requestJson(`${this.bleBase}/displays/${sensorId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
  }

  async getSamplesLatest(): Promise<SampleRow | null> {
    const payload = await this.requestJson<SamplesPayload>(
      `${this.samplesBase}/latest`,
    );
    if (!payload.configured) return null;
    return payload.row ?? null;
  }

  async getSamplesHistory(seconds: number): Promise<SampleRow[]> {
    const payload = await this.requestJson<SamplesPayload>(
      `${this.samplesBase}?seconds=${encodeURIComponent(String(seconds))}`,
    );
    if (!payload.configured) return [];
    return payload.rows ?? [];
  }

  private async requestJson<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await this.fetchFn(url, init);
    const text = await response.text();
    const data = text ? (JSON.parse(text) as T) : ({} as T);
    if (!response.ok) {
      const detail =
        data && typeof data === 'object' && 'detail' in data
          ? String((data as { detail: unknown }).detail)
          : `${response.status} ${response.statusText}`;
      throw new Error(detail);
    }
    return data;
  }
}
