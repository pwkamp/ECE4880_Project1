import { thermometerSource } from '../datasource';
import {
  SENSOR_IDS,
  supportsSim,
  type ThermometerFrame,
} from '../datasource/types';

interface Props {
  frame: ThermometerFrame;
}

/**
 * Demo control panel. Lets a presenter script the spec's edge cases live
 * without real hardware: unplug a sensor, flip the box switch, drive a sensor
 * off-scale. Hidden automatically when the data source is real hardware that
 * does not implement the simulation controls.
 */
export function DebugPanel({ frame }: Props) {
  if (!supportsSim(thermometerSource)) return null;
  const sim = thermometerSource;

  return (
    <section className="panel panel-debug">
      <h2>Demo controls (mock only)</h2>

      <div className="debug-group">
        <span className="debug-label">Third-box power switch</span>
        <div className="btn-row">
          <button
            type="button"
            disabled={frame.switchState === 'on'}
            onClick={() => sim.simSetSwitch('on')}
          >
            Switch ON
          </button>
          <button
            type="button"
            disabled={frame.switchState === 'off'}
            onClick={() => sim.simSetSwitch('off')}
          >
            Switch OFF
          </button>
        </div>
      </div>

      {SENSOR_IDS.map((id) => {
        const r = frame.readings[id];
        return (
          <div className="debug-group" key={id}>
            <span className="debug-label">Sensor {id}</span>
            <div className="btn-row">
              <button
                type="button"
                disabled={!r.connected}
                onClick={() => sim.simSetConnected(id, false)}
              >
                Unplug
              </button>
              <button
                type="button"
                disabled={r.connected}
                onClick={() => sim.simSetConnected(id, true)}
              >
                Plug in
              </button>
              <button type="button" onClick={() => sim.simPin(id, 60)}>
                Spike to 60 °C
              </button>
              <button type="button" onClick={() => sim.simPin(id, 0)}>
                Drop to 0 °C
              </button>
              <button type="button" onClick={() => sim.simPin(id, null)}>
                Resume normal
              </button>
            </div>
          </div>
        );
      })}

      <div className="btn-row">
        <button type="button" onClick={() => sim.simReset()}>
          Reset all
        </button>
      </div>
    </section>
  );
}
