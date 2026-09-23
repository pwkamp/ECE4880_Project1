import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, test } from 'vitest';
import { AlertSettings } from './AlertSettings';
import { DEFAULT_ALERT_CONFIG, defaultRecipient, type AlertConfig } from '../lib/alerts';

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
});

function type(el: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
  setter?.call(el, value);
  el.dispatchEvent(new Event('input', { bubbles: true }));
}

function harness(initial: AlertConfig = DEFAULT_ALERT_CONFIG) {
  let config = initial;
  function render(next: AlertConfig) {
    config = next;
    root.render(<AlertSettings config={next} unit="C" onChange={render} />);
  }
  act(() => render(config));
  return { get config() { return config; } };
}

test('does not add a recipient until Save is clicked', async () => {
  const state = harness();
  const input = container.querySelector('#alert-destination') as HTMLInputElement;
  await act(async () => type(input, 'alerts@example.com'));
  expect(state.config.recipients).toEqual([]);

  await act(async () => {
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(state.config.recipients[0].destination).toBe('alerts@example.com');
});

test('rejects an invalid address on Save', async () => {
  const state = harness();
  await act(async () => type(container.querySelector('#alert-destination') as HTMLInputElement, 'not-an-email'));
  await act(async () => {
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(state.config.recipients).toEqual([]);
  expect(container.textContent).toContain('Enter a valid email');
});

test('edits address, enabled state, and thresholds independently per recipient', async () => {
  const state = harness({
    enabled: true,
    recipients: [
      defaultRecipient('one@example.com', 'one'),
      defaultRecipient('two@example.com', 'two'),
    ],
  });

  const email = container.querySelector('[aria-label="Recipient 1 email address"]') as HTMLInputElement;
  const max = container.querySelector('[aria-label="Recipient 1 maximum threshold"]') as HTMLInputElement;
  const enabled = container.querySelector('[aria-label="Recipient 1 enabled"]') as HTMLInputElement;
  await act(async () => {
    type(email, 'edited@example.com');
    type(max, '42');
    enabled.click();
  });

  expect(state.config.recipients[0]).toMatchObject({
    destination: 'edited@example.com',
    enabled: false,
    maxC: 42,
  });
  expect(state.config.recipients[1]).toMatchObject({
    destination: 'two@example.com',
    enabled: true,
    maxC: 30,
  });
});

test('adds and removes multiple email recipients', async () => {
  const state = harness();
  await act(async () => {
    type(container.querySelector('#alert-destination') as HTMLInputElement, 'one@example.com');
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  await act(async () => {
    const add = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('+ Add email'));
    add?.click();
  });
  await act(async () => {
    type(container.querySelector('#alert-destination') as HTMLInputElement, 'two@example.com');
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(state.config.recipients.map((item) => item.destination)).toEqual(['one@example.com', 'two@example.com']);

  await act(async () => {
    (container.querySelectorAll('button')[0] as HTMLButtonElement).click();
  });
  expect(state.config.recipients).toHaveLength(1);
});
