import { BleApiClient } from './bleClient';
import {
  frameFromSample,
  type BleStatus,
  type SampleRow,
} from './bleMap';
import type {
  BleConnector,
  SensorId,
  SwitchState,
  ThermometerFrame,
  ThermometerSource,
} from './types';
import { WINDOW_S } from '../lib/chartScroll';

const HISTORY_MS = (WINDOW_S + 10) * 1000;
const DEFAULT_INTERVAL_MS = 1000;

const OFFLINE_STATUS: BleStatus = {
  phase: 'DISCOVERING',
  connected: false,
  ready: false,
  target: null,
  last_error: null,
};

function offlineFrame(now = Date.now()): ThermometerFrame {
  return {
    timestamp: now,
    switchState: 'off',
    readings: {
      1: { sensorId: 1, celsius: null, connected: false, enabled: false },
      2: { sensorId: 2, celsius: null, connected: false, enabled: false },
    },
  };
}

export interface PythonBleSourceOptions {
  client?: BleApiClient;
  intervalMs?: number;
}

/**
 * ThermometerSource backed by the teammate Python BLE connector.
 *
 * Device scan/connect/display go to FastAPI (`/api/v1/ble/*`). Temperature
 * All plotted/current temperatures come from MySQL via `/api/samples`.
 * The browser never asks the ESP32 for current or history data; the backend
 * owns polling, reconnect recovery, and history synchronization.
 */
export class PythonBleSource implements ThermometerSource, BleConnector {
  private readonly client: BleApiClient;
  private readonly intervalMs: number;
  private last: ThermometerFrame = offlineFrame();
  private history: ThermometerFrame[] = [];
  private lastStatus: BleStatus = OFFLINE_STATUS;
  private displays: Record<SensorId, boolean> = { 1: true, 2: true };
  private displayLocks = new Set<SensorId>();
  private confirmedOverrides = new Map<SensorId, { enabled: boolean; until: number }>();
  private lastSample: SampleRow | null = null;
  private listeners = new Set<(frame: ThermometerFrame) => void>();
  private timer: ReturnType<typeof setInterval> | null = null;
  private inFlight = false;

  constructor(options: PythonBleSourceOptions = {}) {
    this.client = options.client ?? new BleApiClient();
    this.intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  }

  getFrame(): ThermometerFrame {
    return this.last;
  }

  getSwitchState(): SwitchState {
    return this.last.switchState;
  }

  getConnectionStatus(): BleStatus {
    return this.lastStatus;
  }

  async setSensorEnabled(sensorId: SensorId, enabled: boolean): Promise<void> {
    if (this.displayLocks.has(sensorId)) return;
    this.displayLocks.add(sensorId);
    try {
      const confirmed = await this.client.setDisplay(sensorId, enabled);
      this.displays[sensorId] = confirmed.enabled;
      this.confirmedOverrides.set(sensorId, {
        enabled: confirmed.enabled,
        until: Date.now() + 3_000,
      });
      this.updateFrame();
      if (confirmed.enabled !== enabled) {
        throw new Error(`Sensor ${sensorId} did not confirm the requested display state`);
      }
    } finally {
      this.displayLocks.delete(sensorId);
    }
  }

  subscribe(listener: (frame: ThermometerFrame) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getHistory(seconds: number): ThermometerFrame[] {
    const cutoff = Date.now() - seconds * 1000;
    return this.history.filter((f) => f.timestamp >= cutoff);
  }

  start(): void {
    if (this.timer) return;
    void this.tick();
    this.timer = setInterval(() => {
      void this.tick();
    }, this.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  async scan() {
    return this.client.scan();
  }

  async connect(address: string, passkey?: string): Promise<void> {
    await this.client.connect(address, passkey);
    this.lastStatus = await this.client.getStatus();
    this.updateFrame();
  }

  async disconnect(): Promise<void> {
    await this.client.disconnect();
    this.lastStatus = await this.client.getStatus();
    this.updateFrame();
  }

  async reconnect(): Promise<void> {
    await this.client.reconnect();
    this.lastStatus = await this.client.getStatus();
    this.updateFrame();
  }

  private async tick(): Promise<void> {
    if (this.inFlight) return;
    this.inFlight = true;
    try {
      try {
        this.lastStatus = await this.client.getStatus();
        for (const display of this.lastStatus.displays ?? []) {
          if (display.sensor_id !== 1 && display.sensor_id !== 2) continue;
          const id = display.sensor_id;
          if (this.displayLocks.has(id)) continue;
          const confirmed = this.confirmedOverrides.get(id);
          if (confirmed && confirmed.enabled !== display.enabled && Date.now() < confirmed.until) {
            continue;
          }
          this.confirmedOverrides.delete(id);
          this.displays[id] = display.enabled;
        }
      } catch {
        this.lastStatus = { ...OFFLINE_STATUS, last_error: 'status unreachable' };
      }

      try {
        this.lastSample = await this.client.getSamplesLatest();
      } catch {
        this.lastSample = null;
      }
      try {
        const rows = await this.client.getSamplesHistory(WINDOW_S);
        this.history = rows.map((row) =>
          frameFromSample(row, this.displays, 'on'),
        );
      } catch {
        // Keep previously read MySQL rows until the sample reader recovers.
      }
      if (this.lastSample) {
        const frame = frameFromSample(this.lastSample, this.displays, 'on');
        const last = this.history[this.history.length - 1];
        if (!last || last.timestamp < frame.timestamp) this.history.push(frame);
        else if (last.timestamp === frame.timestamp) this.history[this.history.length - 1] = frame;
      }
      this.updateFrame();
    } finally {
      this.inFlight = false;
    }
  }

  private updateFrame(): void {
    const switchState: SwitchState = this.lastStatus.ready ? 'on' : 'off';
    this.last = this.lastSample
      ? frameFromSample(this.lastSample, this.displays, switchState)
      : offlineFrame();
    const cutoff = Date.now() - HISTORY_MS;
    while (this.history.length > 0 && this.history[0].timestamp < cutoff) {
      this.history.shift();
    }
    this.emit(this.last);
  }

  private emit(frame: ThermometerFrame): void {
    for (const listener of this.listeners) listener(frame);
  }
}
