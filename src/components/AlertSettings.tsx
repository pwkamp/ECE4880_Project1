import type { AlertConfig } from '../lib/alerts';
import { cToF, type Unit } from '../lib/temperature';

interface Props {
  config: AlertConfig;
  onChange: (config: AlertConfig) => void;
  unit: Unit;
}

function toDisplay(celsius: number, unit: Unit): number {
  return unit === 'C' ? celsius : cToF(celsius);
}

function toCelsius(value: number, unit: Unit): number {
  return unit === 'C' ? value : (value - 32) * (5 / 9);
}

/** Threshold + message + destination configuration for simulated alerts. */
export function AlertSettings({ config, onChange, unit }: Props) {
  const set = (patch: Partial<AlertConfig>) => onChange({ ...config, ...patch });

  return (
    <section className="panel">
      <h2>Threshold alerts</h2>
      <p className="panel-hint">
        Simulated only &mdash; no message is actually sent.
      </p>

      <label className="toggle-row">
        <span>Alerting</span>
        <input
          type="checkbox"
          checked={config.enabled}
          onChange={(e) => set({ enabled: e.target.checked })}
        />
        <span className="toggle-state">{config.enabled ? 'on' : 'off'}</span>
      </label>

      <div className="field-grid">
        <label>
          Max threshold ({`°${unit}`})
          <input
            type="number"
            value={round1(toDisplay(config.maxC, unit))}
            onChange={(e) =>
              set({ maxC: toCelsius(Number(e.target.value), unit) })
            }
          />
        </label>
        <label>
          Min threshold ({`°${unit}`})
          <input
            type="number"
            value={round1(toDisplay(config.minC, unit))}
            onChange={(e) =>
              set({ minC: toCelsius(Number(e.target.value), unit) })
            }
          />
        </label>
      </div>

      <label className="field-block">
        Max-exceeded message
        <input
          type="text"
          value={config.maxMessage}
          onChange={(e) => set({ maxMessage: e.target.value })}
        />
      </label>
      <label className="field-block">
        Min-exceeded message
        <input
          type="text"
          value={config.minMessage}
          onChange={(e) => set({ minMessage: e.target.value })}
        />
      </label>
      <label className="field-block">
        Destination (phone or email)
        <input
          type="text"
          value={config.destination}
          onChange={(e) => set({ destination: e.target.value })}
        />
      </label>
    </section>
  );
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}
