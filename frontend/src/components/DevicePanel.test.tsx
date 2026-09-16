import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { DevicePanelInner } from './DevicePanel';
import type { BleConnector, ThermometerSource } from '../datasource/types';

let container: HTMLDivElement;
let root: Root;

function makeSource(overrides: Partial<BleConnector> = {}): ThermometerSource & BleConnector {
  return {
    getFrame: () => ({
      timestamp: Date.now(),
      switchState: 'off',
      readings: {
        1: { sensorId: 1, celsius: null, connected: false, enabled: false },
        2: { sensorId: 2, celsius: null, connected: false, enabled: false },
      },
    }),
    getSwitchState: () => 'off',
    setSensorEnabled: () => undefined,
    subscribe: () => () => undefined,
    getHistory: () => [],
    start: () => undefined,
    stop: () => undefined,
    scan: vi.fn(async () => []),
    connect: vi.fn(async () => undefined),
    disconnect: vi.fn(async () => undefined),
    reconnect: vi.fn(async () => undefined),
    getConnectionStatus: () => ({
      phase: 'AUTHENTICATION_REQUIRED',
      connected: false,
      ready: false,
      desired_connected: true,
      credential_state: 'MISSING',
      target: { name: 'Thermometer-3603B2', address: 'CC:7B:5C:36:03:B2' },
      last_error: 'a six-digit passkey is required',
    }),
    ...overrides,
  };
}

function button(label: string): HTMLButtonElement {
  const found = Array.from(container.querySelectorAll('button')).find(
    (candidate) => candidate.textContent === label,
  );
  if (!found) throw new Error(`missing ${label} button`);
  return found;
}

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test('sends the passkey for the auto-discovered target using the single Connect button', async () => {
  const connect = vi.fn(async () => undefined);
  await act(async () => root.render(<DevicePanelInner source={makeSource({ connect })} />));

  const input = container.querySelector('input') as HTMLInputElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  await act(async () => {
    setter?.call(input, '012345');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  expect(button('Connect').disabled).toBe(false);
  await act(async () => button('Connect').click());

  expect(connect).toHaveBeenCalledWith('CC:7B:5C:36:03:B2', '012345');
  expect(container.querySelectorAll('button').length).toBe(3);
});

test('scan populates a dropdown and Connect uses the selected address without a saved PIN', async () => {
  const connect = vi.fn(async () => { throw new Error('a six-digit passkey is required'); });
  const scan = vi.fn(async () => [
    { name: 'Thermometer-A', address: 'AA:BB:CC:DD:EE:01', rssi: -40 },
    { name: 'Thermometer-B', address: 'AA:BB:CC:DD:EE:02', rssi: -50 },
  ]);
  const source = makeSource({
    connect,
    scan,
    getConnectionStatus: () => ({
      phase: 'SELECTION_REQUIRED', connected: false, ready: false,
      target: null, last_error: null,
    }),
  });
  await act(async () => root.render(<DevicePanelInner source={source} />));
  await act(async () => button('Scan').click());
  const dropdown = container.querySelector('select') as HTMLSelectElement;
  expect(dropdown.options.length).toBe(2);
  await act(async () => {
    dropdown.value = 'AA:BB:CC:DD:EE:02';
    dropdown.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await act(async () => button('Connect').click());
  expect(connect).toHaveBeenCalledWith('AA:BB:CC:DD:EE:02', undefined);
  expect(container.textContent).toContain('Pairing passkey');
});

test('Disconnect calls the backend even while it is waiting for a PIN', async () => {
  const disconnect = vi.fn(async () => undefined);
  await act(async () => root.render(<DevicePanelInner source={makeSource({ disconnect })} />));
  await act(async () => button('Disconnect').click());
  expect(disconnect).toHaveBeenCalledOnce();
});

test('shows the completed database history recovery result', async () => {
  const source = makeSource({
    getConnectionStatus: () => ({
      phase: 'CONNECTED', connected: true, ready: true,
      target: { name: 'Thermometer-Test', address: 'AA:BB:CC:DD:EE:FF' },
      last_error: null,
      history_sync: {
        state: 'COMPLETE', expected_counts: [300, 300],
        retrieved_counts: [300, 300], sample_count: 300,
        elapsed_seconds: 5.2, persisted: true,
      },
    }),
  });
  await act(async () => root.render(<DevicePanelInner source={source} />));
  expect(container.textContent).toContain('300 seconds saved to MySQL in 5.2 s');
});
