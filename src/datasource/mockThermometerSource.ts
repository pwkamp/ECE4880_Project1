import {
  SENSOR_IDS,
  type SensorId,
  type SensorReading,
  type SwitchState,
  type ThermometerFrame,
  type ThermometerSimControls,
  type ThermometerSource,
} from './types';

/** How often the box produces a frame. The spec requires 1 Hz. */
const TICK_MS = 1000;

/** How much history to retain internally (a bit more than the 300 s window). */
const HISTORY_MS = 360_000;

interface SensorModel {
  /** The underlying "true" temperature in Celsius, before pin/offset. */
  walkC: number;
  /** Long-run mean the walk reverts toward. */
  meanC: number;
  connected: boolean;
  enabled: boolean;
  /** When set, the reading is forced to this value (debug off-scale tests). */
  pinnedC: number | null;
}

/** Standard normal via Box-Muller. */
function randn(): number {
  let u = 0;
  let v = 0;
  while (u === 0) u = Math.random();
  while (v === 0) v = Math.random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/**
 * A believable "third box" simulator.
 *
 * Temperatures follow a mean-reverting random walk (Ornstein-Uhlenbeck style),
 * so the trace looks like a real chart-recorder line rather than white noise.
 * The debug controls let a presenter script the spec's edge cases live.
 */
export class MockThermometerSource
  implements ThermometerSource, ThermometerSimControls
{
  private switchState: SwitchState = 'on';

  private readonly sensors: Record<SensorId, SensorModel> = {
    1: { walkC: 21.5, meanC: 21.5, connected: true, enabled: true, pinnedC: null },
    2: { walkC: 23.4, meanC: 23.4, connected: true, enabled: true, pinnedC: null },
  };

  private history: ThermometerFrame[] = [];

  private readonly listeners = new Set<(frame: ThermometerFrame) => void>();

  private timer: ReturnType<typeof setInterval> | null = null;

  constructor() {
    this.seedHistory();
  }

  // --- ThermometerSource -------------------------------------------------

  getFrame(): ThermometerFrame {
    const last = this.history[this.history.length - 1];
    return last ?? this.buildFrame(Date.now());
  }

  getSwitchState(): SwitchState {
    return this.switchState;
  }

  setSensorEnabled(sensorId: SensorId, enabled: boolean): void {
    this.sensors[sensorId].enabled = enabled;
    // Reflect the change immediately rather than waiting for the next tick,
    // so the "< 1 s" requirement holds even at the start of a tick interval.
    this.emit(this.appendFrame(Date.now()));
  }

  subscribe(listener: (frame: ThermometerFrame) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  getHistory(seconds: number): ThermometerFrame[] {
    const cutoff = Date.now() - seconds * 1000;
    return this.history.filter((f) => f.timestamp >= cutoff);
  }

  start(): void {
    if (this.timer !== null) return;
    this.timer = setInterval(() => {
      this.emit(this.appendFrame(Date.now()));
    }, TICK_MS);
  }

  stop(): void {
    if (this.timer !== null) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  // --- ThermometerSimControls (debug only) -----------------------------

  simSetSwitch(state: SwitchState): void {
    this.switchState = state;
    this.emit(this.appendFrame(Date.now()));
  }

  simSetConnected(sensorId: SensorId, connected: boolean): void {
    this.sensors[sensorId].connected = connected;
    this.emit(this.appendFrame(Date.now()));
  }

  simPin(sensorId: SensorId, celsius: number | null): void {
    this.sensors[sensorId].pinnedC = celsius;
    this.emit(this.appendFrame(Date.now()));
  }

  simReset(): void {
    this.switchState = 'on';
    for (const id of SENSOR_IDS) {
      const s = this.sensors[id];
      s.connected = true;
      s.enabled = true;
      s.pinnedC = null;
    }
    this.emit(this.appendFrame(Date.now()));
  }

  // --- internals -------------------------------------------------------

  /** Advance the underlying random walk by one step. */
  private advanceWalk(): void {
    for (const id of SENSOR_IDS) {
      const s = this.sensors[id];
      const reversion = 0.02 * (s.meanC - s.walkC);
      s.walkC += reversion + 0.08 * randn();
    }
  }

  private buildReading(sensorId: SensorId): SensorReading {
    const s = this.sensors[sensorId];
    const hasData =
      this.switchState === 'on' && s.connected && s.enabled;
    const celsius = hasData ? s.pinnedC ?? s.walkC : null;
    return {
      sensorId,
      celsius: celsius === null ? null : round2(celsius),
      connected: s.connected,
      enabled: s.enabled,
    };
  }

  private buildFrame(timestamp: number): ThermometerFrame {
    return {
      timestamp,
      switchState: this.switchState,
      readings: {
        1: this.buildReading(1),
        2: this.buildReading(2),
      },
    };
  }

  /** Advance the walk, append a fresh frame, trim old history, return it. */
  private appendFrame(timestamp: number): ThermometerFrame {
    this.advanceWalk();
    const frame = this.buildFrame(timestamp);
    this.history.push(frame);
    const cutoff = timestamp - HISTORY_MS;
    while (this.history.length > 0 && this.history[0].timestamp < cutoff) {
      this.history.shift();
    }
    return frame;
  }

  private emit(frame: ThermometerFrame): void {
    for (const listener of this.listeners) listener(frame);
  }

  /**
   * Fill the last 300 s of history with a plausible trace so the chart is
   * populated the moment the app loads (spec: within 10 s of startup).
   * Assumes the box "has been on" for that period.
   */
  private seedHistory(): void {
    const now = Date.now();
    this.history = [];
    for (let t = now - 300_000; t <= now; t += TICK_MS) {
      this.advanceWalk();
      this.history.push(this.buildFrame(t));
    }
  }
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}
