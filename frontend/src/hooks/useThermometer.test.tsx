import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, test, vi } from 'vitest';
import { thermometerSource } from '../datasource';
import type { ThermometerFrame } from '../datasource/types';
import { useThermometer, WINDOW_SECONDS } from './useThermometer';

afterEach(() => vi.restoreAllMocks());

test('passes a recovered 300-second database history through to the graph', async () => {
  const now = Date.now();
  const frames: ThermometerFrame[] = Array.from({ length: 300 }, (_, index) => ({
    timestamp: now - (309 - index) * 1000,
    switchState: 'on',
    readings: {
      1: { sensorId: 1, celsius: 20 + index / 100, connected: true, enabled: true },
      2: { sensorId: 2, celsius: 22 + index / 100, connected: true, enabled: true },
    },
  }));
  let publish: ((frame: ThermometerFrame) => void) | undefined;
  let available: ThermometerFrame[] = [];
  vi.spyOn(thermometerSource, 'getHistory').mockImplementation((seconds) => {
    expect(seconds).toBe(WINDOW_SECONDS);
    return available;
  });
  vi.spyOn(thermometerSource, 'getFrame').mockReturnValue(frames[299]);
  vi.spyOn(thermometerSource, 'subscribe').mockImplementation((listener) => {
    publish = listener;
    return () => { publish = undefined; };
  });
  vi.spyOn(thermometerSource, 'start').mockImplementation(() => undefined);

  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  function Probe() {
    const { history } = useThermometer();
    return <span>{history.length}:{history[0]?.readings[1].celsius}</span>;
  }
  try {
    await act(async () => { root.render(<Probe />); });
    expect(container.textContent).toBe('0:');
    available = frames;
    await act(async () => { publish?.(frames[299]); });
    expect(container.textContent).toBe('300:20');
  } finally {
    await act(async () => { root.unmount(); });
    container.remove();
  }
});
