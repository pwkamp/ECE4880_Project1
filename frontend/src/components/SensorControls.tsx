import { useState } from 'react';
import { thermometerSource } from '../datasource';
import {
  SENSOR_IDS, supportsBle, type SensorId, type ThermometerFrame,
  type ThermometerSource,
} from '../datasource/types';

interface Props {
  frame: ThermometerFrame;
  source?: ThermometerSource;
}

/**
 * Virtual buttons: turn each sensor's display on or off from the computer,
 * the software equivalent of the physical button on the third box.
 */
export function SensorControls({ frame, source = thermometerSource }: Props) {
  const [pending, setPending] = useState<Record<SensorId, boolean>>({ 1: false, 2: false });
  const [error, setError] = useState<string | null>(null);
  const ble = supportsBle(source) ? source : null;

  async function changeDisplay(sensorId: SensorId, enabled: boolean): Promise<void> {
    if (pending[sensorId]) return;
    setPending((current) => ({ ...current, [sensorId]: true }));
    setError(null);
    try {
      await source.setSensorEnabled(sensorId, enabled);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Display command failed');
    } finally {
      setPending((current) => ({ ...current, [sensorId]: false }));
    }
  }

  return (
    <section className="panel">
      <h2>Sensor display</h2>
      <p className="panel-hint">
        Virtual button
      </p>
      {error ? <p className="device-error" role="alert">{error}</p> : null}
      <div className="control-rows">
        {SENSOR_IDS.map((id) => {
          const enabled = frame.readings[id].enabled;
          return (
            <label className="toggle-row" key={id}>
              <span className={`sensor-name sensor-${id}`}>Sensor {id}</span>
              <input
                type="checkbox"
                checked={enabled}
                disabled={pending[id] || (ble !== null && !ble.getConnectionStatus().ready)}
                onChange={(e) => void changeDisplay(id, e.target.checked)}
              />
              <span className="toggle-state">
                {pending[id] ? 'Updating...' : enabled ? 'on' : 'off'}
              </span>
            </label>
          );
        })}
      </div>
    </section>
  );
}
