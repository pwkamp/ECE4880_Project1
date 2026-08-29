import { thermometerSource } from '../datasource';
import { SENSOR_IDS, type ThermometerFrame } from '../datasource/types';

interface Props {
  frame: ThermometerFrame;
}

/**
 * Virtual buttons: turn each sensor's display on or off from the computer,
 * the software equivalent of the physical button on the third box.
 */
export function SensorControls({ frame }: Props) {
  return (
    <section className="panel">
      <h2>Sensor display</h2>
      <p className="panel-hint">
        Virtual button &mdash; same effect as pressing the button on the box.
      </p>
      <div className="control-rows">
        {SENSOR_IDS.map((id) => {
          const enabled = frame.readings[id].enabled;
          return (
            <label className="toggle-row" key={id}>
              <span>Sensor {id}</span>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) =>
                  thermometerSource.setSensorEnabled(id, e.target.checked)
                }
              />
              <span className="toggle-state">{enabled ? 'on' : 'off'}</span>
            </label>
          );
        })}
      </div>
    </section>
  );
}
