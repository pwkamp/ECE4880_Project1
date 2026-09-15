import { useEffect, useState } from 'react';
import { thermometerSource } from '../datasource';
import { connectionHint, type BleDevice } from '../datasource/bleMap';
import { supportsBle, type BleConnector, type ThermometerSource } from '../datasource/types';

type BleSource = ThermometerSource & BleConnector;

function phaseLabel(phase: string, ready: boolean, autoDiscover?: boolean): string {
  if (ready) return 'Connected';
  switch (phase) {
    case 'DISCONNECTED':
      return autoDiscover
        ? 'Not connected — waiting for device'
        : 'Not connected — click Scan';
    case 'DISCOVERING':
      return 'Scanning…';
    case 'SELECTION_REQUIRED':
      return 'Pick a device below';
    case 'AUTHENTICATION_REQUIRED':
      return 'Passkey required';
    case 'PAIRING':
      return 'Pairing…';
    case 'CONNECTING':
    case 'VERIFYING':
      return 'Connecting…';
    case 'RECONNECTING':
      return 'Reconnecting…';
    case 'CONNECTED':
      return 'Connected';
    default:
      return phase;
  }
}

/**
 * Scan / connect UI for the teammate Python BLE connector.
 * Hidden when the mock data source is active.
 */
export function DevicePanel() {
  if (!supportsBle(thermometerSource)) return null;
  return <DevicePanelInner source={thermometerSource} />;
}

function DevicePanelInner({ source: ble }: { source: BleSource }) {

  const [phase, setPhase] = useState(ble.getConnectionStatus().phase);
  const [status, setStatus] = useState(ble.getConnectionStatus());
  const [devices, setDevices] = useState<BleDevice[]>([]);
  const [passkey, setPasskey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      const next = ble.getConnectionStatus();
      setStatus(next);
      setPhase(next.phase);
      if (next.last_error) setError(next.last_error);
    }, 1000);
    return () => clearInterval(id);
  }, [ble]);

  async function run(fn: () => Promise<void>): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'request failed');
    } finally {
      setBusy(false);
      const next = ble.getConnectionStatus();
      setStatus(next);
      setPhase(next.phase);
    }
  }

  return (
    <section className="panel">
      <h2>Device connection</h2>
      <p className="panel-hint">{connectionHint(status)}</p>
      <p className="device-status">
        <strong>{phaseLabel(phase, status.ready, status.auto_discover_on_start)}</strong>
        {status.target ? ` — ${status.target.name}` : ''}
      </p>
      {error ? <p className="device-error">{error}</p> : null}

      <div className="btn-row">
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            run(async () => {
              setDevices(await ble.scan());
            })
          }
        >
          Scan
        </button>
        <button
          type="button"
          disabled={busy || !status.connected}
          onClick={() => run(() => ble.disconnect())}
        >
          Disconnect
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => ble.reconnect())}
        >
          Reconnect
        </button>
      </div>

      <label className="field-block">
        Pairing passkey (6 digits, if asked)
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={passkey}
          onChange={(e) => setPasskey(e.target.value)}
          placeholder="123456"
        />
      </label>

      {devices.length === 0 ? (
        <p className="panel-hint">No scan results yet.</p>
      ) : (
        <ul className="device-list">
          {devices.map((d) => (
            <li key={d.address}>
              <span>
                {d.name}{' '}
                <code>{d.address}</code>
                {d.rssi != null ? ` (${d.rssi} dBm)` : ''}
              </span>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  run(() => ble.connect(d.address, passkey || undefined))
                }
              >
                Connect
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
