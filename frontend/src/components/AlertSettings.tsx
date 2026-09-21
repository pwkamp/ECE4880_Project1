import { useState, type FormEvent } from 'react';
import type { AlertConfig } from '../lib/alerts';
import { cToF, type Unit } from '../lib/temperature';

interface Props {
  config: AlertConfig;
  onChange: (config: AlertConfig) => void;
  unit: Unit;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function toDisplay(celsius: number, unit: Unit): number {
  return unit === 'C' ? celsius : cToF(celsius);
}

function toCelsius(value: number, unit: Unit): number {
  return unit === 'C' ? value : (value - 32) * (5 / 9);
}

/** Threshold + message + destination configuration for alerts. */
export function AlertSettings({ config, onChange, unit }: Props) {
  const set = (patch: Partial<AlertConfig>) => onChange({ ...config, ...patch });
  const saved = config.destinations;
  const [draftEmail, setDraftEmail] = useState('');
  const [adding, setAdding] = useState(saved.length === 0);
  const [emailError, setEmailError] = useState<string | null>(null);

  function saveEmail(e: FormEvent) {
    e.preventDefault();
    const draft = draftEmail.trim().toLowerCase();
    if (!EMAIL.test(draft)) {
      setEmailError('Enter a valid email, then click Save.');
      return;
    }
    if (saved.includes(draft)) {
      setEmailError('That address is already on the list.');
      return;
    }
    set({ destinations: [...saved, draft] });
    setDraftEmail('');
    setAdding(false);
    setEmailError(null);
  }

  function removeEmail(email: string) {
    const next = saved.filter((item) => item !== email);
    set({ destinations: next });
    if (next.length === 0) setAdding(true);
  }

  return (
    <section className="panel">
      <h2>Threshold alerts</h2>
      <p className="panel-hint">
        Sends email through Gmail SMTP when a threshold is crossed.
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

      <div className="field-block">
        <span>Alert emails</span>
        {saved.length > 0 ? (
          <ul className="email-list">
            {saved.map((email) => (
              <li key={email} className="email-chip">
                <span>{email}</span>
                <button type="button" onClick={() => removeEmail(email)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {adding ? (
          <form className="email-save" onSubmit={saveEmail} noValidate>
            <div className="email-save-row">
              <input
                id="alert-destination"
                type="email"
                placeholder="you@example.com"
                value={draftEmail}
                onChange={(e) => {
                  setDraftEmail(e.target.value);
                  setEmailError(null);
                }}
                autoComplete="email"
              />
              <button type="submit">Save</button>
            </div>
          </form>
        ) : (
          <button
            type="button"
            className="email-add"
            onClick={() => {
              setAdding(true);
              setEmailError(null);
            }}
          >
            + Add email
          </button>
        )}

        {emailError ? (
          <p className="email-status email-status-err" role="alert">
            {emailError}
          </p>
        ) : saved.length > 0 ? (
          <p className="email-status email-status-ok" role="status">
            Alerts will be sent to {saved.join(', ')}
          </p>
        ) : (
          <p className="email-status">
            Type an address and click Save. Alerts are not sent until it is confirmed.
          </p>
        )}
      </div>
    </section>
  );
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}
