import type { SensorId, SensorReading, SwitchState, ThermometerFrame } from './types';

export interface BleDevice {
  name: string;
  address: string;
  rssi: number | null;
}

export interface BleStatus {
  phase: string;
  connected: boolean;
  ready: boolean;
  target: { name: string; address: string } | null;
  last_error: string | null;
}

export interface BleSensor {
  sensor_id: number;
  temperature_c: number | null;
  visible_state: string;
  display_enabled: boolean;
  connected: boolean;
}

export interface BleCurrent {
  available: boolean;
  received_at_utc: string | null;
  snapshot: { sensors: BleSensor[] } | null;
  error: string | null;
}

export type SampleStatus = 'VALID' | 'DISCONNECTED' | 'NOT_RETRIEVED' | 'MISSING';

export interface SampleRow {
  observed_at_utc: string;
  sensor1_c: number | string | null;
  sensor1_status: SampleStatus;
  sensor2_c: number | string | null;
  sensor2_status: SampleStatus;
}

const EMPTY_READING = (sensorId: SensorId): SensorReading => ({
  sensorId,
  celsius: null,
  connected: false,
  enabled: false,
});

function celsiusOrNull(value: number | string | null | undefined): number | null {
  if (value == null || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function readingFromBle(sensor: BleSensor | undefined, id: SensorId): SensorReading {
  if (!sensor) return EMPTY_READING(id);
  const connected = sensor.connected && sensor.visible_state !== 'DISCONNECTED';
  const enabled = sensor.display_enabled && sensor.visible_state === 'ON';
  const celsius =
    connected && enabled ? celsiusOrNull(sensor.temperature_c) : null;
  return { sensorId: id, celsius, connected, enabled };
}

function readingFromSample(
  celsiusRaw: number | string | null,
  status: SampleStatus,
  enabled: boolean,
  id: SensorId,
): SensorReading {
  const connected = status !== 'DISCONNECTED';
  const celsius = status === 'VALID' ? celsiusOrNull(celsiusRaw) : null;
  return { sensorId: id, celsius, connected, enabled };
}

/** Map a BLE /current payload plus /status into a console frame. */
export function frameFromBle(
  current: BleCurrent,
  status: BleStatus,
  now = Date.now(),
): ThermometerFrame {
  const live = current.available && status.ready && current.snapshot != null;
  const timestamp = current.received_at_utc
    ? Date.parse(current.received_at_utc)
    : now;
  if (!live) {
    return {
      timestamp: Number.isFinite(timestamp) ? timestamp : now,
      switchState: 'off',
      readings: { 1: EMPTY_READING(1), 2: EMPTY_READING(2) },
    };
  }
  const byId = new Map(current.snapshot!.sensors.map((s) => [s.sensor_id, s]));
  return {
    timestamp: Number.isFinite(timestamp) ? timestamp : now,
    switchState: 'on',
    readings: {
      1: readingFromBle(byId.get(1), 1),
      2: readingFromBle(byId.get(2), 2),
    },
  };
}

/** Map one temperature_samples row into a console frame. */
export function frameFromSample(
  row: SampleRow,
  displays: Record<SensorId, boolean>,
  switchState: SwitchState,
  now = Date.now(),
): ThermometerFrame {
  const timestamp = Date.parse(row.observed_at_utc);
  return {
    timestamp: Number.isFinite(timestamp) ? timestamp : now,
    switchState,
    readings: {
      1: readingFromSample(row.sensor1_c, row.sensor1_status, displays[1], 1),
      2: readingFromSample(row.sensor2_c, row.sensor2_status, displays[2], 2),
    },
  };
}
