/**
 * The contract between the computer app and the "third box".
 *
 * Everything the UI knows about the hardware goes through a
 * `ThermometerSource`. The app ships with `MockThermometerSource`; a real
 * implementation (`RealThermometerSource`) that talks to the physical box over
 * HTTP / WebSocket / serial can be dropped in later without touching any UI or
 * business-logic code. See src/datasource/index.ts for the swap point.
 *
 * ---------------------------------------------------------------------------
 * FOR THE HARDWARE / EMBEDDED TEAM
 * ---------------------------------------------------------------------------
 * The real box needs to expose, at roughly 1 Hz, the data described by
 * `ThermometerFrame` below:
 *
 *   - a timestamp
 *   - the position of the power switch ('on' | 'off')
 *   - for each of the two sensors:
 *       celsius     the temperature reading, or null if there is none
 *       connected   is the sensor physically plugged in?
 *       enabled     is that sensor's display turned on? (the button state)
 *
 * `celsius` should be null (not 0, not a stale value) whenever the box cannot
 * produce a fresh reading: switch off, sensor unplugged, or sensor display
 * turned off. Send raw Celsius; the app handles C/F conversion and clamping.
 */

export type SensorId = 1 | 2;

export const SENSOR_IDS: readonly SensorId[] = [1, 2];

export type SwitchState = 'on' | 'off';

/** One sensor's state at one instant. */
export interface SensorReading {
  sensorId: SensorId;
  /**
   * Temperature in degrees Celsius, or null when there is no reading:
   * power switch off, sensor unplugged, or the sensor's display is off.
   */
  celsius: number | null;
  /** True when the sensor is physically plugged in. */
  connected: boolean;
  /** True when the sensor's display is enabled (physical or virtual button). */
  enabled: boolean;
}

/** A complete snapshot of the third box at one instant. Emitted at ~1 Hz. */
export interface ThermometerFrame {
  /** Epoch milliseconds (Date.now()). */
  timestamp: number;
  /** Position of the third box's power switch. */
  switchState: SwitchState;
  /** One entry per sensor id. */
  readings: Record<SensorId, SensorReading>;
}

/**
 * The data source. The UI depends only on this interface.
 *
 * All methods are synchronous here for simplicity; a networked real
 * implementation would keep the same shape and resolve its internal cache from
 * the transport, emitting `subscribe` callbacks as frames arrive.
 */
export interface ThermometerSource {
  /** The most recent frame. Always returns something (for first render). */
  getFrame(): ThermometerFrame;

  /** Convenience accessor for just the switch position. */
  getSwitchState(): SwitchState;

  /**
   * Virtual button press: turn a sensor's display on or off from the computer.
   * Must be reflected in the stream within 1 second.
   */
  setSensorEnabled(sensorId: SensorId, enabled: boolean): void;

  /**
   * Subscribe to the ~1 Hz frame stream. Returns an unsubscribe function.
   * The listener is NOT called synchronously on subscribe; call `getFrame()`
   * for the current value.
   */
  subscribe(listener: (frame: ThermometerFrame) => void): () => void;

  /**
   * Frames covering roughly the last `seconds` seconds, oldest first, ~1 Hz.
   * Used to seed the chart on startup so the operator does not watch it build
   * up from empty. A real implementation would return whatever backlog the box
   * (or a local buffer) can provide, or an empty array if none.
   */
  getHistory(seconds: number): ThermometerFrame[];

  /** Begin producing frames. */
  start(): void;

  /** Stop producing frames and release timers/connections. */
  stop(): void;
}

/**
 * Out-of-band controls used ONLY by the demo/debug panel to script hardware
 * scenarios that a real operator would create by hand (unplugging a probe,
 * flipping the switch, heating a sensor past 50 C).
 *
 * A real `ThermometerSource` is not required to implement this. The debug panel
 * feature-detects it with `supportsSim()`.
 */
export interface ThermometerSimControls {
  /** Move the simulated power switch. */
  simSetSwitch(state: SwitchState): void;
  /** Plug / unplug a simulated sensor. */
  simSetConnected(sensorId: SensorId, connected: boolean): void;
  /**
   * Pin a sensor to an absolute Celsius value (e.g. 60 or 0 to test off-scale
   * rendering), or pass null to resume the normal random walk.
   */
  simPin(sensorId: SensorId, celsius: number | null): void;
  /** Restore switch on, both sensors connected, no pins. */
  simReset(): void;
}

export function supportsSim(
  source: ThermometerSource,
): source is ThermometerSource & ThermometerSimControls {
  return typeof (source as Partial<ThermometerSimControls>).simReset === 'function';
}
