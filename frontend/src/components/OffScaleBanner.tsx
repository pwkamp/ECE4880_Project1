import { SENSOR_IDS, type SensorId, type ThermometerFrame } from '../datasource/types';
import { isOffScale, SCALE_C } from '../lib/temperature';

interface Props {
  frame: ThermometerFrame;
}

/** Flashing notice when a live reading is outside the 10-50 °C chart window. */
export function OffScaleBanner({ frame }: Props) {
  const offenders = SENSOR_IDS.filter((id) => isOffScale(frame.readings[id].celsius));
  if (offenders.length === 0) return null;

  return (
    <div className="offscale-banner" role="alert">
      <span className="offscale-flash">OFF-SCALE</span>
      <span className="offscale-detail">{detail(offenders, frame)}</span>
    </div>
  );
}

function detail(ids: SensorId[], frame: ThermometerFrame): string {
  const parts = ids.map((id) => {
    const c = frame.readings[id].celsius as number;
    const dir = c > SCALE_C.max ? 'high' : 'low';
    return `Sensor ${id} ${dir} (${c.toFixed(1)} °C)`;
  });
  return `${parts.join(' · ')} - outside the 10-50 °C chart window`;
}
