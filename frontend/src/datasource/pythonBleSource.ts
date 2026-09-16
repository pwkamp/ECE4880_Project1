import { BleApiClient } from './bleClient';
import {
  frameFromBle,
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

const HISTORY_MS = 360_000;
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
 * samples are read from MySQL via `/api/samples` when that reader is
 * configured; otherwise the live BLE `/current` snapshot is used.
 */
export class PythonBleSource implements ThermometerSource, BleConnector {
  private readonly client: BleApiClient;
  private readonly intervalMs: number;
  private last: ThermometerFrame = offlineFrame();
  private history: ThermometerFrame[] = [];
  private lastStatus: BleStatus = OFFLINE_STATUS;
  private displays: Record<SensorId, boolean> = { 1: true, 2: true };
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

  setSensorEnabled(sensorId: SensorId, enabled: boolean): void {
    this.displays[sensorId] = enabled;
    const prev = this.last.readings[sensorId];
    this.last = {
      ...this.last,
      readings: {
        ...this.last.readings,
        [sensorId]: {
          ...prev,
          enabled,
          celsius: enabled ? prev.celsius : null,
        },
      },
    };
    this.emit(this.last);
    void this.client.setDisplay(sensorId, enabled).catch(() => undefined);
  }

  subscribe(listener: (frame: ThermometerFrame) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getHistory(seconds: number): ThermometerFrame[] {
    const now = this.last.timestamp || Date.now();
    const cutoff = now - seconds * 1000;
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
    await this.tick();
  }

  async disconnect(): Promise<void> {
    await this.client.disconnect();
    await this.tick();
  }

  async reconnect(): Promise<void> {
    await this.client.reconnect();
    await this.tick();
  }

  private async tick(): Promise<void> {
    if (this.inFlight) return;
    this.inFlight = true;
    try {
      try {
        this.lastStatus = await this.client.getStatus();
      } catch {
        this.lastStatus = { ...OFFLINE_STATUS, last_error: 'status unreachable' };
      }

      try {
        const current = await this.client.getCurrent();
        if (current.snapshot) {
          for (const sensor of current.snapshot.sensors) {
            if (sensor.sensor_id === 1 || sensor.sensor_id === 2) {
              this.displays[sensor.sensor_id] = sensor.display_enabled;
            }
          }
        }
        const sample = await this.client.getSamplesLatest();
        if (this.history.length === 0) {
          await this.seedHistoryFromDb();
        }
        const switchState: SwitchState = this.lastStatus.ready ? 'on' : 'off';
        const frame = sample
          ? frameFromSample(sample, this.displays, switchState)
          : frameFromBle(current, this.lastStatus);
        this.ingest(frame);
      } catch {
        this.ingest(offlineFrame());
      }
    } finally {
      this.inFlight = false;
    }
  }

  private async seedHistoryFromDb(): Promise<void> {
    let rows: SampleRow[] = [];
    try {
      rows = await this.client.getSamplesHistory(300);
    } catch {
      return;
    }
    if (rows.length === 0) return;
    const switchState: SwitchState = this.lastStatus.ready ? 'on' : 'off';
    this.history = rows.map((row) =>
      frameFromSample(row, this.displays, switchState),
    );
  }

  private ingest(frame: ThermometerFrame): void {
    this.last = frame;
    const prev = this.history[this.history.length - 1];
    if (prev && prev.timestamp === frame.timestamp) {
      this.history[this.history.length - 1] = frame;
    } else {
      this.history.push(frame);
    }
    const cutoff = frame.timestamp - HISTORY_MS;
    while (this.history.length > 0 && this.history[0].timestamp < cutoff) {
      this.history.shift();
    }
    this.emit(frame);
  }

  private emit(frame: ThermometerFrame): void {
    for (const listener of this.listeners) listener(frame);
  }
}
