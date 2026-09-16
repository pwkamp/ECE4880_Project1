import type { SensorId, ThermometerFrame } from '../datasource/types';
import { readoutFor, readoutMessage } from '../lib/readout';
import { SCALE_C, toUnit, type Unit, unitSymbol } from '../lib/temperature';

interface Props {
  frame: ThermometerFrame;
  sensorId: SensorId;
  unit: Unit;
}

/** The large, glanceable real-time value for one sensor. */
export function RealtimeReadout({ frame, sensorId, unit }: Props) {
  const readout = readoutFor(frame, sensorId);

  if (readout.kind !== 'ok') {
    return (
      <div className="readout">
        <div className="readout-label">Sensor {sensorId}</div>
        <div className="readout-message">{readoutMessage(readout)}</div>
      </div>
    );
  }

  const value = toUnit(readout.celsius, unit);
  const offScale =
    readout.celsius > SCALE_C.max || readout.celsius < SCALE_C.min;

  return (
    <div className="readout">
      <div className="readout-label">Sensor {sensorId}</div>
      <div className="readout-value">
        {value.toFixed(1)}
        <span className="readout-unit">{unitSymbol(unit)}</span>
      </div>
      {offScale && (
        <div className="readout-note">off chart scale</div>
      )}
    </div>
  );
}
