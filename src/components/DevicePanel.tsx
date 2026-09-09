import { useEffect, useState } from 'react';
import { thermometerSource } from '../datasource';
import type { BleDevice } from '../datasource/bleMap';
import { supportsBle, type BleConnector, type ThermometerSource } from '../datasource/types';

type BleSource = ThermometerSource & BleConnector;

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
  const [devices, setDevices] = useState<BleDevice[]>([]);
  const [passkey, setPasskey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      const status = ble.getConnectionStatus();
      setPhase(status.phase);
      if (status.last_error) setError(status.last_error);
    }, 1000);
    return () => clearInterval(id);
  }, [ble]);

  const status = ble.getConnectionStatus();

  async function run(fn: () => Promise<void>): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'request failed');
    } finally {
      setBusy(false);
      setPhase(ble.getConnectionStatus().phase);
    }
  }

  return (
    <section className="panel">
      <h2>Device connection</h2>
      <p className="panel-hint">
        Scan and connect through the Python BLE service. Temperatures are read
        from the database when it is configured, otherwise from the live snapshot.
      </p>
      <p className="device-status">
        <strong>{phase}</strong>
        {status.target ? ` — ${status.target.name}` : ''}
        {status.ready ? ' (ready)' : ''}
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
