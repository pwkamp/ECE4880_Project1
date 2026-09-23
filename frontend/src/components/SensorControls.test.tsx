import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { SensorControls } from './SensorControls';
import type { ThermometerFrame, ThermometerSource } from '../datasource/types';

let container: HTMLDivElement;
let root: Root;

function frame(enabled: boolean): ThermometerFrame {
  return {
    timestamp: Date.now(),
    switchState: 'on',
    readings: {
      1: { sensorId: 1, celsius: 20, connected: true, enabled },
      2: { sensorId: 2, celsius: 22, connected: true, enabled: true },
    },
  };
}

function disconnectedFrame(): ThermometerFrame {
  const value = frame(false);
  value.readings[1] = {
    sensorId: 1,
    celsius: null,
    connected: false,
    enabled: false,
  };
  return value;
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

test('locks a display toggle until the backend confirms it', async () => {
  let confirm!: () => void;
  const setSensorEnabled = vi.fn(() => new Promise<void>((resolve) => { confirm = resolve; }));
  const source = { setSensorEnabled } as unknown as ThermometerSource;
  await act(async () => root.render(<SensorControls frame={frame(true)} source={source} />));
  const checkbox = container.querySelectorAll('input')[0] as HTMLInputElement;

  await act(async () => checkbox.click());
  expect(setSensorEnabled).toHaveBeenCalledWith(1, false);
  expect(checkbox.disabled).toBe(true);
  expect(container.textContent).toContain('Updating...');
  checkbox.click();
  expect(setSensorEnabled).toHaveBeenCalledOnce();

  await act(async () => {
    confirm();
    await Promise.resolve();
    root.render(<SensorControls frame={frame(false)} source={source} />);
  });
  expect(checkbox.disabled).toBe(false);
  expect(checkbox.checked).toBe(false);
});

test('reports a failed display command and unlocks the toggle', async () => {
  const source = {
    setSensorEnabled: vi.fn(async () => { throw new Error('ESP32 did not confirm'); }),
  } as unknown as ThermometerSource;
  await act(async () => root.render(<SensorControls frame={frame(true)} source={source} />));
  const checkbox = container.querySelectorAll('input')[0] as HTMLInputElement;
  await act(async () => checkbox.click());
  expect(container.textContent).toContain('ESP32 did not confirm');
  expect(checkbox.disabled).toBe(false);
  expect(checkbox.checked).toBe(true);
});

test('does not allow a disconnected physical sensor to be enabled', async () => {
  const setSensorEnabled = vi.fn();
  const source = { setSensorEnabled } as unknown as ThermometerSource;
  await act(async () =>
    root.render(<SensorControls frame={disconnectedFrame()} source={source} />),
  );

  const checkbox = container.querySelectorAll('input')[0] as HTMLInputElement;
  expect(checkbox.disabled).toBe(true);
  expect(checkbox.checked).toBe(false);
  expect(container.textContent).toContain('unavailable');

  checkbox.click();
  expect(setSensorEnabled).not.toHaveBeenCalled();
});
