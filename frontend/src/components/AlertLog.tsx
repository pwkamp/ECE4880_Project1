import type { AlertEvent, AlertSource } from '../lib/alertEngine';
import type { DeliveryState } from '../hooks/useAlertNotifier';
import { formatTemp, type Unit } from '../lib/temperature';

interface Props {
  alerts: AlertEvent[];
  unit: Unit;
  delivery?: Record<string, DeliveryState>;
}

const SOURCE_LABEL: Record<AlertSource, string> = {
  SENSOR_1: 'Sensor 1',
  SENSOR_2: 'Sensor 2',
  AVERAGE: 'Sensor average',
};

function line(a: AlertEvent, unit: Unit): string {
  const t = new Date(a.timestamp).toLocaleTimeString();
  const what =
    a.transition === 'HIGH'
      ? 'above max'
      : a.transition === 'LOW'
        ? 'below min'
        : 'back in range';
  return `${t} — ${SOURCE_LABEL[a.source]} ${what} (${formatTemp(a.celsius, unit)})`;
}

function deliveryLabel(state: DeliveryState | undefined): string | null {
  if (!state) return null;
  if (state === 'pending') return 'sending…';
  if (state.ok) return state.status === 'logged' ? 'logged (console)' : 'sent';
  if (state.status === 'unreachable') return 'service unreachable';
  return state.reason ? `failed — ${state.reason}` : 'failed';
}

/** The visible stand-in for "a text/email would have been sent here". */
export function AlertLog({ alerts, unit, delivery }: Props) {
  return (
    <section className="panel">
      <h2>Alert activity</h2>
      {alerts.length === 0 ? (
        <p className="panel-hint">No alerts triggered yet.</p>
      ) : (
        <ul className="alert-list">
          {alerts.map((a, i) => {
            const badge = a.transition === 'NORMAL' ? null : deliveryLabel(delivery?.[a.id]);
            return (
              <li
                key={a.id}
                className={i === 0 ? 'alert-item alert-item-latest' : 'alert-item'}
              >
                <div className="alert-item-head">
                  <span className="alert-tag">
                    {a.transition === 'NORMAL' ? 'RECOVERED' : 'SIMULATED ALERT'}
                  </span>
                  <span className="alert-meta">{line(a, unit)}</span>
                </div>
                <div className="alert-item-body">
                  Would send to <strong>{a.destination}</strong>: &ldquo;
                  {a.message}&rdquo;
                </div>
                {badge && <div className="alert-item-delivery">SMS: {badge}</div>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
