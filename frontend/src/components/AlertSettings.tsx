import { useState, type FormEvent } from 'react';
import {
  defaultRecipient,
  type AlertConfig,
  type AlertRecipientConfig,
} from '../lib/alerts';
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

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

/** Editable, independently enabled thresholds for every email recipient. */
export function AlertSettings({ config, onChange, unit }: Props) {
  const [draftEmail, setDraftEmail] = useState('');
  const [adding, setAdding] = useState(config.recipients.length === 0);
  const [emailError, setEmailError] = useState<string | null>(null);

  function setRecipient(id: string, patch: Partial<AlertRecipientConfig>) {
    onChange({
      ...config,
      recipients: config.recipients.map((recipient) =>
        recipient.id === id ? { ...recipient, ...patch } : recipient,
      ),
    });
  }

  function saveEmail(event: FormEvent) {
    event.preventDefault();
    const destination = draftEmail.trim().toLowerCase();
    if (!EMAIL.test(destination)) {
      setEmailError('Enter a valid email, then click Save.');
      return;
    }
    if (config.recipients.some((item) => item.destination === destination)) {
      setEmailError('That address is already on the list.');
      return;
    }
    const id = `recipient-${Date.now()}-${config.recipients.length + 1}`;
    onChange({ ...config, recipients: [...config.recipients, defaultRecipient(destination, id)] });
    setDraftEmail('');
    setAdding(false);
    setEmailError(null);
  }

  function removeRecipient(id: string) {
    const recipients = config.recipients.filter((item) => item.id !== id);
    onChange({ ...config, recipients });
    if (recipients.length === 0) setAdding(true);
  }

  return (
    <section className="panel">
      <h2>Threshold alerts</h2>
      <p className="panel-hint">
        Sends email through Gmail SMTP when a recipient&apos;s threshold is crossed.
      </p>

      <label className="toggle-row">
        <span>Alerting</span>
        <input
          type="checkbox"
          aria-label="Alerting enabled"
          checked={config.enabled}
          onChange={(event) => onChange({ ...config, enabled: event.target.checked })}
        />
        <span className="toggle-state">{config.enabled ? 'on' : 'off'}</span>
      </label>

      <div className="recipient-list">
        {config.recipients.map((recipient, index) => {
          const validEmail = EMAIL.test(recipient.destination);
          const validRange = recipient.minC < recipient.maxC;
          return (
            <fieldset className="recipient-card" key={recipient.id}>
              <legend>Email recipient {index + 1}</legend>
              <label className="field-block">
                Email address
                <input
                  type="email"
                  aria-label={`Recipient ${index + 1} email address`}
                  value={recipient.destination}
                  onChange={(event) => setRecipient(recipient.id, { destination: event.target.value.trim().toLowerCase() })}
                />
              </label>
              {!validEmail ? <p className="email-status email-status-err" role="alert">Enter a valid email address.</p> : null}
              <label className="toggle-row">
                <span>Recipient enabled</span>
                <input
                  type="checkbox"
                  aria-label={`Recipient ${index + 1} enabled`}
                  checked={recipient.enabled}
                  onChange={(event) => setRecipient(recipient.id, { enabled: event.target.checked })}
                />
                <span className="toggle-state">{recipient.enabled ? 'on' : 'off'}</span>
              </label>
              <div className="field-grid">
                <label>
                  Max threshold ({`°${unit}`})
                  <input
                    type="number"
                    aria-label={`Recipient ${index + 1} maximum threshold`}
                    value={round1(toDisplay(recipient.maxC, unit))}
                    onChange={(event) => setRecipient(recipient.id, { maxC: toCelsius(Number(event.target.value), unit) })}
                  />
                </label>
                <label>
                  Min threshold ({`°${unit}`})
                  <input
                    type="number"
                    aria-label={`Recipient ${index + 1} minimum threshold`}
                    value={round1(toDisplay(recipient.minC, unit))}
                    onChange={(event) => setRecipient(recipient.id, { minC: toCelsius(Number(event.target.value), unit) })}
                  />
                </label>
              </div>
              {!validRange ? <p className="email-status email-status-err" role="alert">Minimum must be below maximum.</p> : null}
              <label className="field-block">
                Max-exceeded message
                <input
                  type="text"
                  value={recipient.maxMessage}
                  onChange={(event) => setRecipient(recipient.id, { maxMessage: event.target.value })}
                />
              </label>
              <label className="field-block">
                Min-exceeded message
                <input
                  type="text"
                  value={recipient.minMessage}
                  onChange={(event) => setRecipient(recipient.id, { minMessage: event.target.value })}
                />
              </label>
              <button type="button" onClick={() => removeRecipient(recipient.id)}>Remove recipient</button>
            </fieldset>
          );
        })}
      </div>

      <div className="field-block">
        <span>Alert emails</span>
        {adding ? (
          <form className="email-save" onSubmit={saveEmail} noValidate>
            <div className="email-save-row">
              <input
                id="alert-destination"
                type="email"
                placeholder="you@example.com"
                value={draftEmail}
                onChange={(event) => {
                  setDraftEmail(event.target.value);
                  setEmailError(null);
                }}
                autoComplete="email"
              />
              <button type="submit">Save</button>
            </div>
          </form>
        ) : (
          <button type="button" className="email-add" onClick={() => setAdding(true)}>
            + Add email
          </button>
        )}
        {emailError ? <p className="email-status email-status-err" role="alert">{emailError}</p> : null}
      </div>
    </section>
  );
}
