import { SENSOR_IDS, type SensorId, type ThermometerFrame } from '../datasource/types';

export interface AlertConfig {
  enabled: boolean;
  /** Thresholds are stored in Celsius regardless of the display unit. */
  maxC: number;
  minC: number;
  maxMessage: string;
  minMessage: string;
  /** Free-text phone number or email. Not validated, never actually sent. */
  destination: string;
}

export const DEFAULT_ALERT_CONFIG: AlertConfig = {
  enabled: true,
  maxC: 30,
  minC: 15,
  maxMessage: 'Temperature high: sensor above the configured maximum.',
  minMessage: 'Temperature low: sensor below the configured minimum.',
  destination: '+1 555 0123',
};

export type Bound = 'max' | 'min';

/**
 * Which (sensor, bound) pairs are currently in violation. Used to fire an
 * alert once per crossing rather than every second while exceeded.
 */
export type AlertLatch = Record<string, boolean>;

export const EMPTY_LATCH: AlertLatch = {};

export interface SimulatedAlert {
  id: string;
  timestamp: number;
  sensorId: SensorId;
  bound: Bound;
  celsius: number;
  message: string;
  destination: string;
}

function key(sensorId: SensorId, bound: Bound): string {
  return `${sensorId}:${bound}`;
}

export interface EvaluateResult {
  latch: AlertLatch;
  fired: SimulatedAlert[];
}

/**
 * Pure threshold check for one frame.
 *
 * Rules:
 *  - Only crossings fire (not-violating -> violating), so a sustained
 *    excursion produces exactly one alert.
 *  - Missing data (celsius == null) leaves the latch untouched: when the
 *    reading returns still-exceeded, that is not a new crossing.
 *  - Returning inside the band clears the latch, arming the next crossing.
 */
export function evaluateAlerts(
  frame: ThermometerFrame,
  config: AlertConfig,
  prev: AlertLatch,
): EvaluateResult {
  const latch: AlertLatch = { ...prev };
  const fired: SimulatedAlert[] = [];
  if (!config.enabled) return { latch, fired };

  for (const sensorId of SENSOR_IDS) {
    const celsius = frame.readings[sensorId].celsius;
    if (celsius == null) continue;

    const checks: Array<{ bound: Bound; violating: boolean; message: string }> = [
      {
        bound: 'max',
        violating: celsius > config.maxC,
        message: config.maxMessage,
      },
      {
        bound: 'min',
        violating: celsius < config.minC,
        message: config.minMessage,
      },
    ];

    for (const { bound, violating, message } of checks) {
      const k = key(sensorId, bound);
      if (violating && !latch[k]) {
        fired.push({
          id: `${k}-${frame.timestamp}`,
          timestamp: frame.timestamp,
          sensorId,
          bound,
          celsius,
          message,
          destination: config.destination,
        });
      }
      latch[k] = violating;
    }
  }

  return { latch, fired };
}
