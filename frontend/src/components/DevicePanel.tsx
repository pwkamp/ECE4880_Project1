import { useEffect, useState } from 'react';
import { thermometerSource } from '../datasource';
import { connectionHint, type BleDevice } from '../datasource/bleMap';
import { supportsBle, type BleConnector, type ThermometerSource } from '../datasource/types';

type BleSource = ThermometerSource & BleConnector;

function phaseLabel(phase: string, ready: boolean, autoDiscover?: boolean): string {
  if (ready) return 'Connected';
  switch (phase) {
    case 'DISCONNECTED':
      return autoDiscover ? 'Not connected - waiting for device' : 'Not connected - click Scan';
    case 'DISCOVERING':
      return 'Scanning...';
    case 'SELECTION_REQUIRED':
      return 'Pick a device below';
    case 'AUTHENTICATION_REQUIRED':
      return 'Passkey required';
    case 'PAIRING':
      return 'Pairing...';
    case 'CONNECTING':
    case 'VERIFYING':
      return 'Connecting...';
    case 'RECONNECTING':
      return 'Reconnecting...';
    case 'CONNECTED':
      return 'Connected';
    default:
      return phase;
  }
}

export function DevicePanel() {
  if (!supportsBle(thermometerSource)) return null;
  return <DevicePanelInner source={thermometerSource} />;
}

export function DevicePanelInner({ source: ble }: { source: BleSource }) {
  const [status, setStatus] = useState(ble.getConnectionStatus());
  const [devices, setDevices] = useState<BleDevice[]>([]);
  const [selectedAddress, setSelectedAddress] = useState(
    ble.getConnectionStatus().target?.address ?? '',
  );
  const [needsPasskeyFor, setNeedsPasskeyFor] = useState<string | null>(null);
  const [passkey, setPasskey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const id = setInterval(() => {
      const next = ble.getConnectionStatus();
      setStatus(next);
      setSelectedAddress((address) => address || next.target?.address || '');
    }, 1000);
    return () => clearInterval(id);
  }, [ble]);

  const available = [...devices];
  if (status.target && !available.some((device) => device.address === status.target?.address)) {
    available.unshift({ ...status.target, rssi: null });
  }
  const selected = selectedAddress || (available.length === 1 ? available[0].address : '');
  const needsPasskey =
    needsPasskeyFor === selected ||
    (status.target?.address === selected &&
      (status.credential_state === 'MISSING' || status.credential_state === 'REJECTED') &&
      status.phase === 'AUTHENTICATION_REQUIRED');

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
      setSelectedAddress((address) => address || next.target?.address || '');
    }
  }

  async function connect(): Promise<void> {
    if (!selected) return;
    const credential = passkey.trim();
    if (needsPasskey && !/^\d{6}$/.test(credential)) {
      setError('Enter the six-digit firmware passkey.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await ble.connect(selected, needsPasskey ? credential : undefined);
      setNeedsPasskeyFor(null);
      setPasskey('');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'connection failed';
      if (/passkey|PIN|credential/i.test(message)) setNeedsPasskeyFor(selected);
      setError(message);
    } finally {
      setBusy(false);
      setStatus(ble.getConnectionStatus());
    }
  }

  return (
    <section className="panel">
      <h2>Device connection</h2>
      <p className="panel-hint">{connectionHint(status)}</p>
      <p className="device-status">
        <strong>{phaseLabel(status.phase, status.ready, status.auto_discover_on_start)}</strong>
        {status.target ? ` - ${status.target.name}` : ''}
      </p>
      {status.ready && status.history_sync ? (
        <p className="panel-hint" role="status">
          {status.history_sync.state === 'RUNNING'
            ? `Recovering ESP32 history: ${Math.round((status.history_sync.progress ?? 0) * 100)}%`
            : status.history_sync.state === 'COMPLETE'
              ? `History recovered: ${status.history_sync.sample_count ?? 0} seconds ${status.history_sync.persisted ? 'saved to MySQL' : 'retrieved (MySQL not configured)'} in ${status.history_sync.elapsed_seconds?.toFixed(1) ?? '?'} s.`
              : `History recovery ${status.history_sync.state.toLowerCase()}: ${status.history_sync.retrieved_counts?.join('/') ?? 'unknown'} of ${status.history_sync.expected_counts?.join('/') ?? 'unknown'} sensor records. ${status.history_sync.failure_reason ?? ''}`}
        </p>
      ) : null}
      {error ?? status.last_error ? (
        <p className="device-error" role="alert">{error ?? status.last_error}</p>
      ) : null}

      <div className="btn-row">
        <button
          type="button"
          disabled={busy}
          onClick={() => void run(async () => {
            const found = await ble.scan();
            setDevices(found);
            setSelectedAddress((address) =>
              address || status.target?.address || found[0]?.address || '',
            );
          })}
        >
          Scan
        </button>
        <button
          type="button"
          disabled={busy || !selected || (needsPasskey && !/^\d{6}$/.test(passkey.trim()))}
          onClick={() => void connect()}
        >
          Connect
        </button>
        <button
          type="button"
          disabled={busy || (!status.connected && !status.desired_connected)}
          onClick={() => void run(() => ble.disconnect())}
        >
          Disconnect
        </button>
      </div>

      <label className="field-block">
        Available thermometers
        <select
          value={selected}
          disabled={busy || available.length === 0}
          onChange={(event) => {
            setSelectedAddress(event.target.value);
            setNeedsPasskeyFor(null);
            setPasskey('');
            setError(null);
          }}
        >
          {available.length === 0 ? <option value="">Scan for devices</option> : null}
          {available.map((device) => (
            <option value={device.address} key={device.address}>
              {device.name} ({device.address})
            </option>
          ))}
        </select>
      </label>
      {needsPasskey ? (
        <label className="field-block">
          Pairing passkey (6 digits)
          <input
            type="text"
            inputMode="numeric"
            autoComplete="off"
            maxLength={6}
            pattern="[0-9]{6}"
            value={passkey}
            onChange={(event) => setPasskey(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !busy) {
                event.preventDefault();
                void connect();
              }
            }}
            placeholder="123456"
          />
        </label>
      ) : null}
    </section>
  );
}
