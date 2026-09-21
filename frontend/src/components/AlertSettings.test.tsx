import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, test } from 'vitest';
import { AlertSettings } from './AlertSettings';
import { DEFAULT_ALERT_CONFIG, type AlertConfig } from '../lib/alerts';

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

test('does not apply the destination until Save is clicked', async () => {
  let config: AlertConfig = { ...DEFAULT_ALERT_CONFIG, destinations: [] };
  function render(next: AlertConfig) {
    root.render(
      <AlertSettings
        config={next}
        unit="C"
        onChange={(updated) => {
          config = updated;
          render(updated);
        }}
      />,
    );
  }
  await act(async () => render(config));
  const input = container.querySelector('#alert-destination') as HTMLInputElement;
  await act(async () => {
    type(input, 'alerts@example.com');
  });
  expect(config.destinations).toEqual([]);

  await act(async () => {
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(config.destinations).toEqual(['alerts@example.com']);
  expect(container.textContent).toContain('Alerts will be sent to');
  expect(container.textContent).toContain('alerts@example.com');
});

test('rejects an invalid address on Save', async () => {
  let config: AlertConfig = { ...DEFAULT_ALERT_CONFIG, destinations: [] };
  await act(async () => {
    root.render(
      <AlertSettings
        config={config}
        unit="C"
        onChange={(updated) => {
          config = updated;
        }}
      />,
    );
  });
  const input = container.querySelector('#alert-destination') as HTMLInputElement;
  await act(async () => {
    type(input, 'not-an-email');
  });
  await act(async () => {
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(config.destinations).toEqual([]);
  expect(container.textContent).toContain('Enter a valid email');
});

test('adds a second email after Save, then + Add email', async () => {
  let config: AlertConfig = { ...DEFAULT_ALERT_CONFIG, destinations: [] };
  function render(next: AlertConfig) {
    root.render(
      <AlertSettings
        config={next}
        unit="C"
        onChange={(updated) => {
          config = updated;
          render(updated);
        }}
      />,
    );
  }
  await act(async () => render(config));
  await act(async () => {
    type(container.querySelector('#alert-destination') as HTMLInputElement, 'one@example.com');
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(config.destinations).toEqual(['one@example.com']);

  await act(async () => {
    const add = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('+ Add email'),
    );
    add?.click();
  });
  await act(async () => {
    type(container.querySelector('#alert-destination') as HTMLInputElement, 'two@example.com');
    (container.querySelector('button[type="submit"]') as HTMLButtonElement).click();
  });
  expect(config.destinations).toEqual(['one@example.com', 'two@example.com']);
});
