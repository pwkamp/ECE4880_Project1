import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import App from './App';

let container: HTMLDivElement;

beforeEach(() => {
  vi.useFakeTimers({ now: Date.now() });
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })));
  container = document.createElement('div');
  document.body.appendChild(container);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  container.remove();
});

test('App mounts, shows both readouts, and ticks without error', async () => {
  await act(async () => {
    createRoot(container).render(<App />);
  });

  expect(container.textContent).toContain('Sensor 1');
  expect(container.textContent).toContain('Sensor 2');
  // Seeded history means a live number is on screen immediately.
  expect(container.textContent).toMatch(/\d+\.\d\s*°C/);

  // Advance several 1 Hz ticks.
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000);
  });

  expect(container.querySelector('.chart-wrap')).not.toBeNull();
  expect(container.textContent).toContain('Threshold alerts');
  expect(container.textContent).toContain('Demo controls (mock only)');
});
