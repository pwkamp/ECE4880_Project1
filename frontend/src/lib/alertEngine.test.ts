import { afterEach, expect, test, vi } from 'vitest';
import { MockThermometerSource } from '../datasource/mockThermometerSource';
import type { SensorId, ThermometerFrame } from '../datasource/types';
import {
  AlertSource,
  INITIAL_ALERT_ENGINE_STATE,
  ruleStateKey,
  sourceCelsius,
  stepAlertEngine,
  type AlertEngineState,
  type AlertEvent,
  type AlertRecipient,
  type AlertRule,
} from './alertEngine';

// --- fixtures --------------------------------------------------------------

function mkFrame(
  s1: number | null,
  s2: number | null = 22,
  timestamp = 1000,
): ThermometerFrame {
  const mk = (sensorId: SensorId, celsius: number | null) => ({
    sensorId,
    celsius,
    connected: true,
    enabled: true,
  });
  return {
    timestamp,
    switchState: 'on',
    readings: { 1: mk(1, s1), 2: mk(2, s2) },
  };
}

function rule(over: Partial<AlertRule> = {}): AlertRule {
  return {
    id: 'r1',
    source: AlertSource.SENSOR_1,
    minC: 10,
    maxC: 30,
    enabled: true,
    highMessage: 'too hot',
    lowMessage: 'too cold',
    clearMessage: 'back to normal',
    ...over,
  };
}

function recipient(over: Partial<AlertRecipient> = {}): AlertRecipient {
  return { id: 'alice', destination: '+1 555 0100', enabled: true, ...over };
}

/** Feed a sequence of sensor-1 values through the engine, return every event. */
function run(
  values: Array<number | null>,
  rules: AlertRule[],
  recipients: AlertRecipient[],
): AlertEvent[] {
  let state: AlertEngineState = INITIAL_ALERT_ENGINE_STATE;
  const events: AlertEvent[] = [];
  values.forEach((v, i) => {
    const step = stepAlertEngine(state, mkFrame(v, 22, 1000 + i), rules, recipients);
    state = step.state;
    events.push(...step.events);
  });
  return events;
}

// --- SCRUM-633: Alert Source Enum ---------------------------------------

test('SCRUM-633: source enum resolves each monitored signal', () => {
  const f = mkFrame(20, 30);
  expect(sourceCelsius(f, AlertSource.SENSOR_1)).toBe(20);
  expect(sourceCelsius(f, AlertSource.SENSOR_2)).toBe(30);
  expect(sourceCelsius(f, AlertSource.AVERAGE)).toBe(25);
});

test('SCRUM-633: AVERAGE needs both sensors, else it reads as no data', () => {
  expect(sourceCelsius(mkFrame(20, null), AlertSource.AVERAGE)).toBeNull();
  expect(sourceCelsius(mkFrame(null, 20), AlertSource.AVERAGE)).toBeNull();
});

// --- SCRUM-622: High Edge Trigger --------------------------------------

test('SCRUM-622: entering HIGH fires exactly one alert', () => {
  const events = run([25, 35], [rule()], [recipient()]);
  expect(events).toHaveLength(1);
  expect(events[0].transition).toBe('HIGH');
  expect(events[0].message).toBe('too hot');
  expect(events[0].celsius).toBe(35);
});

test('SCRUM-622: staying HIGH does not resend (edge- not level-triggered)', () => {
  const events = run([35, 36, 40, 33], [rule()], [recipient()]);
  expect(events.filter((e) => e.transition === 'HIGH')).toHaveLength(1);
});

// --- SCRUM-623: Low Edge Trigger -------------------------------------

test('SCRUM-623: entering LOW fires exactly one alert', () => {
  const events = run([25, 5], [rule()], [recipient()]);
  expect(events).toHaveLength(1);
  expect(events[0].transition).toBe('LOW');
  expect(events[0].message).toBe('too cold');
});

test('SCRUM-623: staying LOW does not resend', () => {
  const events = run([5, 4, 0, 8], [rule()], [recipient()]);
  expect(events.filter((e) => e.transition === 'LOW')).toHaveLength(1);
});

test('SCRUM-623: a direct HIGH -> LOW jump still fires the LOW alert', () => {
  const events = run([35, 5], [rule()], [recipient()]);
  expect(events.map((e) => e.transition)).toEqual(['HIGH', 'LOW']);
});

// --- SCRUM-624: Rearm In Range --------------------------------------

test('SCRUM-624: returning in range resets to NORMAL and rearms', () => {
  const events = run([35, 20, 35], [rule()], [recipient()]);
  expect(events.map((e) => e.transition)).toEqual(['HIGH', 'NORMAL', 'HIGH']);
  expect(events[1].message).toBe('back to normal');
});

test('SCRUM-624: LOW -> NORMAL emits the recovery event', () => {
  const events = run([5, 20], [rule()], [recipient()]);
  expect(events.map((e) => e.transition)).toEqual(['LOW', 'NORMAL']);
});

test('missing data holds state: no fresh crossing when the reading returns', () => {
  const events = run([35, null, 35], [rule()], [recipient()]);
  expect(events.map((e) => e.transition)).toEqual(['HIGH']);
});

// --- SCRUM-621: independent state per (recipient, rule, source) ---------

test('SCRUM-621: two sources on one rule id track state independently', () => {
  const rules = [
    rule({ id: 'shared', source: AlertSource.SENSOR_1 }),
    rule({ id: 'shared', source: AlertSource.SENSOR_2 }),
  ];
  let state: AlertEngineState = INITIAL_ALERT_ENGINE_STATE;
  const events: AlertEvent[] = [];
  // sensor 1 goes high, sensor 2 stays normal, then sensor 2 goes low.
  for (const [i, f] of [mkFrame(35, 22), mkFrame(35, 5)].entries()) {
    const step = stepAlertEngine(state, { ...f, timestamp: 1000 + i }, rules, [
      recipient(),
    ]);
    state = step.state;
    events.push(...step.events);
  }
  expect(events).toHaveLength(2);
  expect(events[0]).toMatchObject({ source: 'SENSOR_1', transition: 'HIGH' });
  expect(events[1]).toMatchObject({ source: 'SENSOR_2', transition: 'LOW' });
});

test('SCRUM-621: two recipients on the same rule each get their own alert', () => {
  const events = run([35], [rule()], [recipient({ id: 'a' }), recipient({ id: 'b' })]);
  expect(events.map((e) => e.recipientId).sort()).toEqual(['a', 'b']);
});

test('SCRUM-621: state key is (recipientId, ruleId, source)', () => {
  expect(ruleStateKey('alice', 'r1', AlertSource.AVERAGE)).toBe('alice::r1::AVERAGE');
});

// --- enable/disable gates --------------------------------------------

test('a disabled rule never fires', () => {
  expect(run([35, 5], [rule({ enabled: false })], [recipient()])).toHaveLength(0);
});

test('a disabled recipient never fires', () => {
  expect(run([35, 5], [rule()], [recipient({ enabled: false })])).toHaveLength(0);
});

// --- fed off the existing mock sensor stream -------------------------

test('runs against the MockThermometerSource frame stream', () => {
  vi.useFakeTimers({ now: 1_700_000_000_000 });
  const src = new MockThermometerSource();
  const rules = [rule({ source: AlertSource.SENSOR_1, maxC: 50 })];
  const recipients = [recipient()];

  let state: AlertEngineState = INITIAL_ALERT_ENGINE_STATE;
  const events: AlertEvent[] = [];
  const unsub = src.subscribe((f) => {
    const step = stepAlertEngine(state, f, rules, recipients);
    state = step.state;
    events.push(...step.events);
  });

  src.start();
  src.simPin(1, 80); // force sensor 1 well above the 50 C max
  vi.advanceTimersByTime(3000); // three more 1 Hz frames, all still HIGH
  src.simPin(1, null);

  expect(events.filter((e) => e.transition === 'HIGH')).toHaveLength(1);

  unsub();
  src.stop();
});

afterEach(() => {
  vi.useRealTimers();
});
