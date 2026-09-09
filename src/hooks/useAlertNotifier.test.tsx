import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import type { AlertEvent } from '../lib/alertEngine';

vi.mock('../lib/notifyClient', () => ({
  notifyAlert: vi.fn(async () => ({ ok: true, status: 'sent' })),
}));

import { notifyAlert } from '../lib/notifyClient';
import { useAlertNotifier } from './useAlertNotifier';

function evt(over: Partial<AlertEvent>): AlertEvent {
  return {
    id: 'e1',
    timestamp: 1000,
    recipientId: 'primary',
    ruleId: 'sensor-1',
    source: 'SENSOR_1',
    transition: 'HIGH',
    destination: '+15005550006',
    message: 'hot',
    celsius: 40,
    ...over,
  };
}

function Harness({ events }: { events: AlertEvent[] }) {
  const statuses = useAlertNotifier(events);
  return <span data-count={Object.keys(statuses).length} />;
}

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  vi.mocked(notifyAlert).mockClear();
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

test('sends once per HIGH event and not again on re-render', async () => {
  await act(async () => {
    root.render(<Harness events={[evt({})]} />);
  });
  expect(notifyAlert).toHaveBeenCalledTimes(1);

  await act(async () => {
    root.render(<Harness events={[evt({})]} />); // new array, same id
  });
  expect(notifyAlert).toHaveBeenCalledTimes(1);
});

test('ignores NORMAL (recovery) transitions', async () => {
  await act(async () => {
    root.render(<Harness events={[evt({ id: 'e2', transition: 'NORMAL' })]} />);
  });
  expect(notifyAlert).not.toHaveBeenCalled();
});

test('records the resolved delivery result', async () => {
  vi.mocked(notifyAlert).mockResolvedValueOnce({ ok: false, status: 'failed', reason: 'boom' });
  let statuses: Record<string, unknown> = {};
  function Probe({ events }: { events: AlertEvent[] }) {
    statuses = useAlertNotifier(events);
    return null;
  }
  await act(async () => {
    root.render(<Probe events={[evt({ id: 'e3' })]} />);
  });
  expect(statuses.e3).toEqual({ ok: false, status: 'failed', reason: 'boom' });
});
