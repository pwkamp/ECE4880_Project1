import type { SimulatedAlert } from '../lib/alerts';
import { formatTemp, type Unit } from '../lib/temperature';

interface Props {
  alerts: SimulatedAlert[];
  unit: Unit;
}

function line(a: SimulatedAlert, unit: Unit): string {
  const dir = a.bound === 'max' ? 'above max' : 'below min';
  const t = new Date(a.timestamp).toLocaleTimeString();
  return `${t} — Sensor ${a.sensorId} ${dir} (${formatTemp(a.celsius, unit)})`;
}

/** The visible stand-in for "a text/email would have been sent here". */
export function AlertLog({ alerts, unit }: Props) {
  return (
    <section className="panel">
      <h2>Alert activity</h2>
      {alerts.length === 0 ? (
        <p className="panel-hint">No alerts triggered yet.</p>
      ) : (
        <ul className="alert-list">
          {alerts.map((a, i) => (
            <li
              key={a.id}
              className={i === 0 ? 'alert-item alert-item-latest' : 'alert-item'}
            >
              <div className="alert-item-head">
                <span className="alert-tag">SIMULATED ALERT</span>
                <span className="alert-meta">{line(a, unit)}</span>
              </div>
              <div className="alert-item-body">
                Would send to <strong>{a.destination}</strong>: &ldquo;
                {a.message}&rdquo;
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
