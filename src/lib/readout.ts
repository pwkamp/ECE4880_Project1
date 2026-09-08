import type { SensorId, ThermometerFrame } from '../datasource/types';

/**
 * What the large real-time numeric display should show for one sensor.
 *
 * Priority order matches the spec: if the box switch is off, nothing is
 * available for either sensor ("no data available"); otherwise an unplugged
 * sensor shows "unplugged sensor"; a sensor whose display was turned off from
 * the UI shows "display off"; otherwise the live number.
 */
export type Readout =
  | { kind: 'ok'; celsius: number }
  | { kind: 'no-data' }
  | { kind: 'unplugged' }
  | { kind: 'display-off' };

export function readoutFor(
  frame: ThermometerFrame,
  sensorId: SensorId,
): Readout {
  if (frame.switchState === 'off') return { kind: 'no-data' };

  const r = frame.readings[sensorId];
  if (!r.connected) return { kind: 'unplugged' };
  if (!r.enabled) return { kind: 'display-off' };
  if (r.celsius == null) return { kind: 'no-data' };
  return { kind: 'ok', celsius: r.celsius };
}

export function readoutMessage(readout: Readout): string {
  switch (readout.kind) {
    case 'no-data':
      return 'no data available';
    case 'unplugged':
      return 'unplugged sensor';
    case 'display-off':
      return 'display off';
    case 'ok':
      return '';
  }
}
