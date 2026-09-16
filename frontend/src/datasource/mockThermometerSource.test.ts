import { beforeEach, expect, test, vi } from 'vitest';
import { MockThermometerSource } from './mockThermometerSource';

beforeEach(() => {
  vi.useFakeTimers({ now: 1_700_000_000_000 });
  return () => vi.useRealTimers();
});

test('seeds ~300 s of history on construction', () => {
  const src = new MockThermometerSource();
  const history = src.getHistory(300);
  expect(history.length).toBeGreaterThanOrEqual(295);
  expect(history.length).toBeLessThanOrEqual(302);
  // Seeded readings are real numbers in a plausible room-temp band.
  for (const f of history) {
    expect(f.readings[1].celsius).not.toBeNull();
    expect(f.readings[1].celsius!).toBeGreaterThan(5);
    expect(f.readings[1].celsius!).toBeLessThan(40);
  }
});

test('unplugging a sensor makes only that sensor null', () => {
  const src = new MockThermometerSource();
  src.simSetConnected(1, false);
  const f = src.getFrame();
  expect(f.readings[1].celsius).toBeNull();
  expect(f.readings[1].connected).toBe(false);
  expect(f.readings[2].celsius).not.toBeNull();
});

test('switch off makes both sensors null; switch on recovers immediately', () => {
  const src = new MockThermometerSource();
  src.simSetSwitch('off');
  let f = src.getFrame();
  expect(f.readings[1].celsius).toBeNull();
  expect(f.readings[2].celsius).toBeNull();

  src.simSetSwitch('on');
  f = src.getFrame();
  expect(f.readings[1].celsius).not.toBeNull();
  expect(f.readings[2].celsius).not.toBeNull();
});

test('pin drives a sensor off-scale', () => {
  const src = new MockThermometerSource();
  src.simPin(2, 60);
  expect(src.getFrame().readings[2].celsius).toBe(60);
  src.simPin(2, null);
  expect(src.getFrame().readings[2].celsius).not.toBe(60);
});

test('setSensorEnabled is reflected without waiting for a tick', () => {
  const src = new MockThermometerSource();
  src.setSensorEnabled(1, false);
  const f = src.getFrame();
  expect(f.readings[1].enabled).toBe(false);
  expect(f.readings[1].celsius).toBeNull();
});

test('subscribe delivers frames on the 1 Hz timer', () => {
  const src = new MockThermometerSource();
  const frames: number[] = [];
  const unsub = src.subscribe((f) => frames.push(f.timestamp));
  src.start();
  vi.advanceTimersByTime(3000);
  expect(frames.length).toBe(3);
  unsub();
  src.stop();
});
