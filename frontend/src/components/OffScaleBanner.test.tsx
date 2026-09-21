import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, test } from 'vitest';
import type { ThermometerFrame } from '../datasource/types';
import { OffScaleBanner } from './OffScaleBanner';

let container: HTMLDivElement;
let root: Root;

function frame(s1: number | null, s2: number | null): ThermometerFrame {
  return {
    timestamp: 1,
    switchState: 'on',
    readings: {
      1: { sensorId: 1, celsius: s1, connected: true, enabled: true },
      2: { sensorId: 2, celsius: s2, connected: true, enabled: true },
    },
  };
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

test('hidden when both sensors are in the chart window', async () => {
  await act(async () => root.render(<OffScaleBanner frame={frame(22, 24)} />));
  expect(container.textContent).toBe('');
});

test('flashes OFF-SCALE for a high reading', async () => {
  await act(async () => root.render(<OffScaleBanner frame={frame(60, 24)} />));
  expect(container.textContent).toContain('OFF-SCALE');
  expect(container.textContent).toContain('Sensor 1');
  expect(container.querySelector('[role="alert"]')).not.toBeNull();
});
