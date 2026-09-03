# SMS Alert Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send a real SMS (via Twilio) to the configured phone number whenever a temperature alert transitions into HIGH or LOW, driven by the app's existing client-side alert engine and mock sensor data.

**Architecture:** A new standalone `server/` Express service exposes `POST /api/notify`. The browser keeps running `stepAlertEngine` against `MockThermometerSource` exactly as today; a new `useAlertNotifier` hook POSTs each HIGH/LOW `AlertEvent` to the service, which validates it, de-duplicates by event id, and dispatches through a pluggable `SmsSender` (`console` logs only — the default; `test`/`live` use the Twilio SDK). Delivery status is shown per-alert in the existing Alert activity panel.

**Tech Stack:** TypeScript, Express 5, `twilio` SDK, `zod`, `tsx` (dev runtime), `concurrently`, `supertest` + Vitest (tests), Vite dev proxy.

**Spec:** `docs/superpowers/specs/2026-09-03-sms-alert-delivery-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Node 18+** (Express 5 requires it).
- **Server relative imports use an explicit `.ts` extension** (`./config.ts`) — required by `module: nodenext` + `allowImportingTsExtensions`. **Frontend imports stay extensionless** (`./alertEngine`) to match existing `src/` code.
- **`verbatimModuleSyntax` is on everywhere** → use `import type { … }` for type-only imports.
- **`erasableSyntaxOnly` is on everywhere** → no TS `enum`, no constructor parameter properties, no namespaces. Use `const` objects + unions (as the codebase already does).
- **All 29 existing tests stay green.** Run `npm test` at each task that touches shared files.
- **No automated test may contact Twilio.** Unit tests use a fake `SmsSender`. `test` mode against Twilio magic numbers is a documented manual step only.
- **The service binds `127.0.0.1` only.**
- **An SMS is sent only when `event.transition` is `HIGH` or `LOW`.** Recovery (`NORMAL`) events are logged in the UI but never sent.
- **Secrets live in `server/.env` (gitignored).** `server/.env.example` is committed with empty values.
- **The `AlertEvent` wire shape is owned separately by the server** (its own zod schema). Do not import from `src/` into `server/`.

`AlertEvent` shape (from `src/lib/alertEngine.ts`, for reference):
```ts
interface AlertEvent {
  id: string;
  timestamp: number;
  recipientId: string;
  ruleId: string;
  source: 'SENSOR_1' | 'SENSOR_2' | 'AVERAGE';
  transition: 'NORMAL' | 'HIGH' | 'LOW';
  destination: string;
  message: string;
  celsius: number;
}
```

---

### Task 1: Backend scaffold + config module

**Files:**
- Create: `server/tsconfig.json`
- Create: `server/.env.example`
- Create: `server/config.ts`
- Test: `server/config.test.ts`
- Modify: `package.json` (dependencies + devDependencies; scripts come in Task 5)
- Modify: `tsconfig.json` (add project reference)
- Modify: `.gitignore` (add `server/.env`)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `loadConfig(env: NodeJS.ProcessEnv): Config`
  - `type SmsMode = 'console' | 'test' | 'live'`
  - `interface TwilioConfig { accountSid: string; authToken: string; fromNumber: string }`
  - `interface Config { mode: SmsMode; port: number; apiToken: string | null; twilio: TwilioConfig | null }`

- [ ] **Step 1: Install dependencies**

```bash
npm install express@^5 twilio zod
npm install -D tsx concurrently supertest @types/supertest @types/express
```

Expected: `package.json` gains the packages, `npm install` completes without peer-dependency errors. If `@types/express` reports a conflict with a bundled type, remove it (`npm uninstall @types/express`) and rely on the bundled types — note which happened in the commit message.

- [ ] **Step 2: Create `server/tsconfig.json`**

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "../node_modules/.tmp/tsconfig.server.tsbuildinfo",
    "target": "es2023",
    "lib": ["ES2023"],
    "types": ["node"],
    "skipLibCheck": true,

    "module": "nodenext",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "resolveJsonModule": true,

    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["**/*.ts"]
}
```

- [ ] **Step 3: Add the project reference in `tsconfig.json`**

Replace the file contents with:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" },
    { "path": "./server/tsconfig.json" }
  ]
}
```

- [ ] **Step 4: Add `server/.env` to `.gitignore`**

Append to `.gitignore` under the `*.local` line:

```
server/.env
```

- [ ] **Step 5: Create `server/.env.example`**

```
# console | test | live   (default: console)
SMS_MODE=console
PORT=8787

# Required for SMS_MODE=test or live.
#   test -> Twilio "Test credentials" SID/token; from-number is the magic +15005550006
#   live -> live SID/token + a real SMS-capable Twilio number
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

# Optional. If set, the frontend must send it as VITE_ALERT_API_TOKEN.
# NOTE: this is compiled into the client bundle, so it is NOT a real secret.
# The service binding to 127.0.0.1 is the actual access control.
ALERT_API_TOKEN=
```

- [ ] **Step 6: Write the failing test — `server/config.test.ts`**

```ts
import { expect, it } from 'vitest';
import { loadConfig } from './config.ts';

it('defaults to console mode when nothing is set', () => {
  const c = loadConfig({} as NodeJS.ProcessEnv);
  expect(c.mode).toBe('console');
  expect(c.port).toBe(8787);
  expect(c.apiToken).toBeNull();
  expect(c.twilio).toBeNull();
});

it('rejects an unknown SMS_MODE', () => {
  expect(() => loadConfig({ SMS_MODE: 'carrier-pigeon' } as NodeJS.ProcessEnv)).toThrow(/SMS_MODE/);
});

it('throws when test mode is missing Twilio vars', () => {
  expect(() => loadConfig({ SMS_MODE: 'test' } as NodeJS.ProcessEnv)).toThrow(/TWILIO_ACCOUNT_SID/);
});

it('accepts a complete live config', () => {
  const c = loadConfig({
    SMS_MODE: 'live',
    TWILIO_ACCOUNT_SID: 'AC1',
    TWILIO_AUTH_TOKEN: 'tok',
    TWILIO_FROM_NUMBER: '+15005550006',
  } as NodeJS.ProcessEnv);
  expect(c.mode).toBe('live');
  expect(c.twilio).toEqual({ accountSid: 'AC1', authToken: 'tok', fromNumber: '+15005550006' });
});

it('reads PORT and ALERT_API_TOKEN overrides', () => {
  const c = loadConfig({ PORT: '9000', ALERT_API_TOKEN: 'sekret' } as NodeJS.ProcessEnv);
  expect(c.port).toBe(9000);
  expect(c.apiToken).toBe('sekret');
});
```

- [ ] **Step 7: Run the test to verify it fails**

Run: `npx vitest run server/config.test.ts`
Expected: FAIL — `Cannot find module './config.ts'`.

- [ ] **Step 8: Implement `server/config.ts`**

```ts
export type SmsMode = 'console' | 'test' | 'live';

export interface TwilioConfig {
  accountSid: string;
  authToken: string;
  fromNumber: string;
}

export interface Config {
  mode: SmsMode;
  port: number;
  apiToken: string | null;
  twilio: TwilioConfig | null;
}

const MODES: readonly SmsMode[] = ['console', 'test', 'live'];

export function loadConfig(env: NodeJS.ProcessEnv): Config {
  const rawMode = env.SMS_MODE ?? 'console';
  if (!MODES.includes(rawMode as SmsMode)) {
    throw new Error(`SMS_MODE must be one of ${MODES.join(', ')} (got "${rawMode}")`);
  }
  const mode = rawMode as SmsMode;

  const port = env.PORT ? Number(env.PORT) : 8787;
  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`PORT must be a positive integer (got "${env.PORT}")`);
  }

  const apiToken = env.ALERT_API_TOKEN && env.ALERT_API_TOKEN.length > 0 ? env.ALERT_API_TOKEN : null;

  let twilio: TwilioConfig | null = null;
  if (mode === 'test' || mode === 'live') {
    const accountSid = env.TWILIO_ACCOUNT_SID ?? '';
    const authToken = env.TWILIO_AUTH_TOKEN ?? '';
    const fromNumber = env.TWILIO_FROM_NUMBER ?? '';
    const missing = ([
      ['TWILIO_ACCOUNT_SID', accountSid],
      ['TWILIO_AUTH_TOKEN', authToken],
      ['TWILIO_FROM_NUMBER', fromNumber],
    ] as const)
      .filter(([, value]) => value.length === 0)
      .map(([name]) => name);
    if (missing.length > 0) {
      throw new Error(`SMS_MODE=${mode} requires: ${missing.join(', ')}`);
    }
    twilio = { accountSid, authToken, fromNumber };
  }

  return { mode, port, apiToken, twilio };
}
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `npx vitest run server/config.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 10: Verify the full build still typechecks**

Run: `npm run build`
Expected: `tsc -b` picks up `server/tsconfig.json` and passes; `vite build` succeeds. If `tsc -b` complains that the referenced project needs `"composite": true`, add `"composite": true` and `"declaration": true` to `server/tsconfig.json`'s `compilerOptions` and re-run.

- [ ] **Step 11: Run the whole test suite**

Run: `npm test`
Expected: 34 passing (29 existing + 5 new).

- [ ] **Step 12: Commit**

```bash
git add server/tsconfig.json server/.env.example server/config.ts server/config.test.ts package.json package-lock.json tsconfig.json .gitignore
git commit -m "$(cat <<'EOF'
Add server scaffold and SMS delivery config module

server/config.ts parses SMS_MODE (console|test|live), PORT, ALERT_API_TOKEN
and Twilio vars, failing fast when test/live is missing credentials.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 2: SMS sender interface + console sender

**Files:**
- Create: `server/sms/types.ts`
- Create: `server/sms/consoleSender.ts`
- Test: `server/sms/consoleSender.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `interface SmsMessage { to: string; body: string }`
  - `interface SmsResult { status: 'sent' | 'logged'; providerId?: string }`
  - `interface SmsSender { send(msg: SmsMessage): Promise<SmsResult> }`
  - `createConsoleSmsSender(): SmsSender`

- [ ] **Step 1: Create `server/sms/types.ts`**

```ts
export interface SmsMessage {
  to: string;
  body: string;
}

export interface SmsResult {
  /** 'sent' via a real provider; 'logged' by the console sender. */
  status: 'sent' | 'logged';
  /** Provider-side id (Twilio message SID) when status is 'sent'. */
  providerId?: string;
}

export interface SmsSender {
  /** Resolves on success; rejects (throws) on provider failure. */
  send(msg: SmsMessage): Promise<SmsResult>;
}
```

- [ ] **Step 2: Write the failing test — `server/sms/consoleSender.test.ts`**

```ts
import { expect, it, vi } from 'vitest';
import { createConsoleSmsSender } from './consoleSender.ts';

it('logs the message and reports "logged"', async () => {
  const spy = vi.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const result = await createConsoleSmsSender().send({ to: '+15005550006', body: 'sensor 1 hot' });
    expect(result).toEqual({ status: 'logged' });
    expect(spy).toHaveBeenCalledOnce();
    expect(String(spy.mock.calls[0][0])).toContain('+15005550006');
    expect(String(spy.mock.calls[0][0])).toContain('sensor 1 hot');
  } finally {
    spy.mockRestore();
  }
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run server/sms/consoleSender.test.ts`
Expected: FAIL — `Cannot find module './consoleSender.ts'`.

- [ ] **Step 4: Implement `server/sms/consoleSender.ts`**

```ts
import type { SmsSender } from './types.ts';

/** A sender that only prints the message. The default in local dev. */
export function createConsoleSmsSender(): SmsSender {
  return {
    async send(msg) {
      console.log(`[sms:console] to=${msg.to} body=${JSON.stringify(msg.body)}`);
      return { status: 'logged' };
    },
  };
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run server/sms/consoleSender.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add server/sms/types.ts server/sms/consoleSender.ts server/sms/consoleSender.test.ts
git commit -m "$(cat <<'EOF'
Add SmsSender interface and console sender

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 3: Twilio sender + sender factory

**Files:**
- Create: `server/sms/twilioSender.ts`
- Create: `server/sms/index.ts`
- Test: `server/sms/index.test.ts`

**Interfaces:**
- Consumes: `Config`, `TwilioConfig` (Task 1); `SmsSender` (Task 2); `createConsoleSmsSender` (Task 2).
- Produces:
  - `createTwilioSmsSender(config: TwilioConfig): SmsSender`
  - `createSmsSender(config: Config): SmsSender`

- [ ] **Step 1: Implement `server/sms/twilioSender.ts`**

```ts
import twilio from 'twilio';
import type { TwilioConfig } from '../config.ts';
import type { SmsSender } from './types.ts';

/** Real delivery through Twilio. Used for both `test` and `live` modes — the
 *  only difference is which credentials config.ts supplied. */
export function createTwilioSmsSender(config: TwilioConfig): SmsSender {
  const client = twilio(config.accountSid, config.authToken);
  return {
    async send(msg) {
      const message = await client.messages.create({
        to: msg.to,
        from: config.fromNumber,
        body: msg.body,
      });
      return { status: 'sent', providerId: message.sid };
    },
  };
}
```

- [ ] **Step 2: Implement `server/sms/index.ts`**

```ts
import type { Config } from '../config.ts';
import { createConsoleSmsSender } from './consoleSender.ts';
import { createTwilioSmsSender } from './twilioSender.ts';
import type { SmsSender } from './types.ts';

export function createSmsSender(config: Config): SmsSender {
  if (config.mode === 'console' || config.twilio === null) {
    return createConsoleSmsSender();
  }
  return createTwilioSmsSender(config.twilio);
}
```

- [ ] **Step 3: Write the test — `server/sms/index.test.ts`**

```ts
import { expect, it, vi } from 'vitest';
import { createSmsSender } from './index.ts';

it('returns a console sender in console mode', async () => {
  const spy = vi.spyOn(console, 'log').mockImplementation(() => {});
  try {
    const sender = createSmsSender({ mode: 'console', port: 8787, apiToken: null, twilio: null });
    await expect(sender.send({ to: '+15005550006', body: 'x' })).resolves.toEqual({ status: 'logged' });
  } finally {
    spy.mockRestore();
  }
});

it('returns a Twilio-backed sender when live config is present', () => {
  const sender = createSmsSender({
    mode: 'live',
    port: 8787,
    apiToken: null,
    twilio: { accountSid: 'AC0000000000000000000000000000000000', authToken: 'tok', fromNumber: '+15005550006' },
  });
  // Constructing the client is offline; we only assert the shape.
  expect(typeof sender.send).toBe('function');
});
```

- [ ] **Step 4: Run the test**

Run: `npx vitest run server/sms/index.test.ts`
Expected: PASS (2 tests). If the second test throws while constructing the Twilio client because the account SID format is rejected, use a valid-looking 34-char SID starting with `AC` (as above); if it still throws, change that test to `expect(() => createSmsSender(liveConfig)).not.toThrow()` wrapped so a throw fails the test explicitly.

- [ ] **Step 5: Run the whole suite**

Run: `npm test`
Expected: green (37 tests).

- [ ] **Step 6: Commit**

```bash
git add server/sms/twilioSender.ts server/sms/index.ts server/sms/index.test.ts
git commit -m "$(cat <<'EOF'
Add Twilio sender and sender factory

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 4: Notify handler

**Files:**
- Create: `server/notify.ts`
- Test: `server/notify.test.ts`

**Interfaces:**
- Consumes: `SmsSender`, `SmsMessage` (Task 2).
- Produces:
  - `const AlertEventSchema` (zod) and `type AlertEventInput = z.infer<typeof AlertEventSchema>`
  - `interface NotifyDeps { sender: SmsSender; seen: Set<string> }`
  - `interface NotifyOutcome { code: 200 | 400 | 502; payload: Record<string, unknown> }`
  - `handleNotify(rawBody: unknown, deps: NotifyDeps): Promise<NotifyOutcome>`

- [ ] **Step 1: Write the failing test — `server/notify.test.ts`**

```ts
import { expect, it } from 'vitest';
import { handleNotify } from './notify.ts';
import type { SmsMessage, SmsSender } from './sms/types.ts';

const base = {
  id: 'e1',
  timestamp: 1000,
  recipientId: 'primary',
  ruleId: 'sensor-1',
  source: 'SENSOR_1',
  transition: 'HIGH',
  destination: '+15005550006',
  message: 'Temperature high: sensor above the configured maximum.',
  celsius: 34.2,
};

function spySender(opts: { throws?: boolean } = {}) {
  const calls: SmsMessage[] = [];
  const sender: SmsSender = {
    async send(msg) {
      calls.push(msg);
      if (opts.throws) throw new Error('provider down');
      return { status: 'sent', providerId: 'SM123' };
    },
  };
  return { sender, calls };
}

it('sends an SMS for a valid HIGH event', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify(base, { sender, seen: new Set() });
  expect(out.code).toBe(200);
  expect(out.payload).toMatchObject({ status: 'sent', providerId: 'SM123' });
  expect(calls).toHaveLength(1);
  expect(calls[0].to).toBe('+15005550006');
  expect(calls[0].body).toContain('Sensor 1');
  expect(calls[0].body).toContain('34.2');
});

it('sends an SMS for a valid LOW event', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify({ ...base, transition: 'LOW' }, { sender, seen: new Set() });
  expect(out.code).toBe(200);
  expect(calls).toHaveLength(1);
});

it('rejects a NORMAL (recovery) transition without calling the sender', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify({ ...base, transition: 'NORMAL' }, { sender, seen: new Set() });
  expect(out.code).toBe(400);
  expect(calls).toHaveLength(0);
});

it('rejects a non-E.164 destination', async () => {
  const { sender, calls } = spySender();
  const out = await handleNotify({ ...base, destination: '5551234' }, { sender, seen: new Set() });
  expect(out.code).toBe(400);
  expect(calls).toHaveLength(0);
});

it('rejects a malformed event (empty message)', async () => {
  const { sender } = spySender();
  const out = await handleNotify({ ...base, message: '' }, { sender, seen: new Set() });
  expect(out.code).toBe(400);
});

it('skips a duplicate event id and does not re-send', async () => {
  const { sender, calls } = spySender();
  const seen = new Set<string>();
  await handleNotify(base, { sender, seen });
  const out = await handleNotify(base, { sender, seen });
  expect(out.code).toBe(200);
  expect(out.payload).toMatchObject({ status: 'skipped', reason: 'duplicate' });
  expect(calls).toHaveLength(1);
});

it('returns 502 when the provider throws', async () => {
  const { sender } = spySender({ throws: true });
  const out = await handleNotify(base, { sender, seen: new Set() });
  expect(out.code).toBe(502);
  expect(out.payload).toMatchObject({ status: 'failed' });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run server/notify.test.ts`
Expected: FAIL — `Cannot find module './notify.ts'`.

- [ ] **Step 3: Implement `server/notify.ts`**

```ts
import { z } from 'zod';
import type { SmsSender } from './sms/types.ts';

export const AlertEventSchema = z.object({
  id: z.string().min(1),
  timestamp: z.number(),
  recipientId: z.string(),
  ruleId: z.string(),
  source: z.enum(['SENSOR_1', 'SENSOR_2', 'AVERAGE']),
  transition: z.enum(['NORMAL', 'HIGH', 'LOW']),
  destination: z.string(),
  message: z.string().min(1),
  celsius: z.number(),
});

export type AlertEventInput = z.infer<typeof AlertEventSchema>;

export interface NotifyDeps {
  sender: SmsSender;
  /** Event ids already delivered. The caller owns and size-caps this. */
  seen: Set<string>;
}

export interface NotifyOutcome {
  code: 200 | 400 | 502;
  payload: Record<string, unknown>;
}

const E164 = /^\+[1-9]\d{1,14}$/;

const SOURCE_LABEL: Record<AlertEventInput['source'], string> = {
  SENSOR_1: 'Sensor 1',
  SENSOR_2: 'Sensor 2',
  AVERAGE: 'Sensor average',
};

function composeBody(event: AlertEventInput): string {
  const text = `${event.message} (${SOURCE_LABEL[event.source]} ${event.celsius.toFixed(1)}°C)`;
  return text.length > 320 ? `${text.slice(0, 317)}...` : text;
}

export async function handleNotify(rawBody: unknown, deps: NotifyDeps): Promise<NotifyOutcome> {
  const parsed = AlertEventSchema.safeParse(rawBody);
  if (!parsed.success) {
    return { code: 400, payload: { status: 'failed', error: 'invalid event', detail: parsed.error.issues } };
  }
  const event = parsed.data;

  if (event.transition !== 'HIGH' && event.transition !== 'LOW') {
    return { code: 400, payload: { status: 'failed', error: 'not a deliverable transition' } };
  }
  if (!E164.test(event.destination)) {
    return { code: 400, payload: { status: 'failed', error: 'destination is not E.164' } };
  }
  if (deps.seen.has(event.id)) {
    return { code: 200, payload: { status: 'skipped', reason: 'duplicate' } };
  }

  try {
    const result = await deps.sender.send({ to: event.destination, body: composeBody(event) });
    deps.seen.add(event.id);
    return { code: 200, payload: { status: result.status, providerId: result.providerId } };
  } catch (err) {
    return { code: 502, payload: { status: 'failed', reason: err instanceof Error ? err.message : String(err) } };
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run server/notify.test.ts`
Expected: PASS (7 tests). If `parsed.error.issues` is not the right property for the installed zod major version, use `parsed.error.format()` instead — the assertion only checks `out.code`.

- [ ] **Step 5: Run the whole suite + build**

Run: `npm test && npm run build`
Expected: green (44 tests); build passes.

- [ ] **Step 6: Commit**

```bash
git add server/notify.ts server/notify.test.ts
git commit -m "$(cat <<'EOF'
Add notify handler: validate, dedupe, compose, dispatch

zod-validates the AlertEvent wire shape, requires a HIGH/LOW transition
and an E.164 destination, de-duplicates by event id, and dispatches
through the injected SmsSender. No retries.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 5: Express app, entrypoint, dev wiring

**Files:**
- Create: `server/app.ts`
- Test: `server/app.test.ts`
- Create: `server/main.ts`
- Modify: `package.json` (`scripts`)
- Modify: `vite.config.ts` (dev proxy)

**Interfaces:**
- Consumes: `Config` (Task 1), `SmsSender` (Task 2), `createSmsSender` (Task 3), `handleNotify` (Task 4), `loadConfig` (Task 1).
- Produces:
  - `createApp(deps: { config: Config; sender: SmsSender }): import('express').Express`
  - Routes: `POST /api/notify`, `GET /api/health`.

- [ ] **Step 1: Write the failing test — `server/app.test.ts`**

```ts
import request from 'supertest';
import { expect, it } from 'vitest';
import { createApp } from './app.ts';
import type { Config } from './config.ts';
import type { SmsSender } from './sms/types.ts';

const consoleConfig: Config = { mode: 'console', port: 8787, apiToken: null, twilio: null };
const okSender: SmsSender = { async send() { return { status: 'logged' }; } };

const validEvent = {
  id: 'e1',
  timestamp: 1000,
  recipientId: 'primary',
  ruleId: 'sensor-1',
  source: 'SENSOR_1',
  transition: 'HIGH',
  destination: '+15005550006',
  message: 'Temperature high.',
  celsius: 40,
};

it('POST /api/notify delivers a valid event', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const res = await request(app).post('/api/notify').send(validEvent);
  expect(res.status).toBe(200);
  expect(res.body.status).toBe('logged');
});

it('POST /api/notify returns 400 for a bad destination', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const res = await request(app).post('/api/notify').send({ ...validEvent, destination: 'nope' });
  expect(res.status).toBe(400);
});

it('GET /api/health reports the mode', async () => {
  const app = createApp({ config: consoleConfig, sender: okSender });
  const res = await request(app).get('/api/health');
  expect(res.status).toBe(200);
  expect(res.body).toEqual({ status: 'ok', mode: 'console' });
});

it('enforces the bearer token when one is configured', async () => {
  const app = createApp({ config: { ...consoleConfig, apiToken: 'sekret' }, sender: okSender });
  const noAuth = await request(app).post('/api/notify').send(validEvent);
  expect(noAuth.status).toBe(401);
  const withAuth = await request(app)
    .post('/api/notify')
    .set('authorization', 'Bearer sekret')
    .send(validEvent);
  expect(withAuth.status).toBe(200);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run server/app.test.ts`
Expected: FAIL — `Cannot find module './app.ts'`.

- [ ] **Step 3: Implement `server/app.ts`**

```ts
import express from 'express';
import type { Config } from './config.ts';
import { handleNotify } from './notify.ts';
import type { SmsSender } from './sms/types.ts';

/** Cap on remembered event ids (oldest evicted first). */
const SEEN_LIMIT = 5000;

export function createApp(deps: { config: Config; sender: SmsSender }) {
  const app = express();
  app.use(express.json({ limit: '16kb' }));

  const seen = new Set<string>();

  if (deps.config.apiToken) {
    const expected = `Bearer ${deps.config.apiToken}`;
    app.use('/api/notify', (req, res, next) => {
      if (req.get('authorization') === expected) {
        next();
        return;
      }
      res.status(401).json({ status: 'failed', error: 'unauthorized' });
    });
  }

  app.post('/api/notify', async (req, res) => {
    const outcome = await handleNotify(req.body, { sender: deps.sender, seen });
    while (seen.size > SEEN_LIMIT) {
      const oldest = seen.values().next().value;
      if (oldest === undefined) break;
      seen.delete(oldest);
    }
    res.status(outcome.code).json(outcome.payload);
  });

  app.get('/api/health', (_req, res) => {
    res.json({ status: 'ok', mode: deps.config.mode });
  });

  return app;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run server/app.test.ts`
Expected: PASS (4 tests).

If TypeScript errors on `import express from 'express'` ("no default export"), change it to `import express from 'express';` with `// @ts-expect-error` only as a last resort — first try adding `"esModuleInterop": true` to `server/tsconfig.json`. If `req`/`res` are typed `any` and lint objects, that is acceptable (strict mode is off repo-wide).

- [ ] **Step 5: Implement `server/main.ts`**

```ts
import { createApp } from './app.ts';
import { loadConfig } from './config.ts';
import { createSmsSender } from './sms/index.ts';

const config = loadConfig(process.env);
const sender = createSmsSender(config);
const app = createApp({ config, sender });

app.listen(config.port, '127.0.0.1', () => {
  console.log(`[alert-service] http://127.0.0.1:${config.port}  (SMS_MODE=${config.mode})`);
});
```

- [ ] **Step 6: Update `package.json` scripts**

Set the `scripts` block to:

```json
  "scripts": {
    "dev": "concurrently -k -n web,api -c blue,green \"vite\" \"npm:dev:server\"",
    "dev:server": "tsx watch server/main.ts",
    "build": "tsc -b && vite build",
    "lint": "oxlint",
    "test": "vitest run",
    "preview": "vite preview"
  }
```

- [ ] **Step 7: Add the dev proxy in `vite.config.ts`**

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8787',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
});
```

- [ ] **Step 8: Manual smoke test**

Run in one terminal: `npm run dev:server`
Expected: logs `[alert-service] http://127.0.0.1:8787  (SMS_MODE=console)`.

In another terminal:
```bash
curl -s localhost:8787/api/health
# {"status":"ok","mode":"console"}

curl -s -XPOST localhost:8787/api/notify -H 'content-type: application/json' -d '{
  "id":"smoke-1","timestamp":1,"recipientId":"primary","ruleId":"sensor-1",
  "source":"SENSOR_1","transition":"HIGH","destination":"+15005550006",
  "message":"Temperature high.","celsius":41.2}'
# {"status":"logged"}
```
Expected: the server terminal prints a `[sms:console] to=+15005550006 …` line. Stop the server (Ctrl-C).

- [ ] **Step 9: Run the whole suite + build**

Run: `npm test && npm run build && npm run lint`
Expected: green (48 tests), build passes, lint clean.

- [ ] **Step 10: Commit**

```bash
git add server/app.ts server/app.test.ts server/main.ts package.json vite.config.ts
git commit -m "$(cat <<'EOF'
Add Express app, entrypoint, and dev wiring

POST /api/notify + GET /api/health, optional bearer-token gate, in-memory
event-id dedupe capped at 5000. `npm run dev` now runs Vite and the
service together; Vite proxies /api to :8787.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 6: Frontend notify client

**Files:**
- Create: `src/vite-env.d.ts`
- Create: `src/lib/notifyClient.ts`
- Test: `src/lib/notifyClient.test.ts`

**Interfaces:**
- Consumes: `AlertEvent` (from `src/lib/alertEngine` — extensionless import).
- Produces:
  - `interface DeliveryResult { ok: boolean; status: string; reason?: string }`
  - `notifyAlert(event: AlertEvent): Promise<DeliveryResult>`

- [ ] **Step 1: Create `src/vite-env.d.ts`**

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ALERT_API_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

- [ ] **Step 2: Write the failing test — `src/lib/notifyClient.test.ts`**

```ts
import { afterEach, expect, test, vi } from 'vitest';
import type { AlertEvent } from './alertEngine';
import { notifyAlert } from './notifyClient';

const event: AlertEvent = {
  id: 'e1',
  timestamp: 1000,
  recipientId: 'primary',
  ruleId: 'sensor-1',
  source: 'SENSOR_1',
  transition: 'HIGH',
  destination: '+15005550006',
  message: 'Temperature high.',
  celsius: 40,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

test('maps a 2xx response to ok', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ status: 'sent', providerId: 'SM1' }), { status: 200 })),
  );
  expect(await notifyAlert(event)).toEqual({ ok: true, status: 'sent' });
});

test('maps a 4xx response to a failure with a reason', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ status: 'failed', error: 'destination is not E.164' }), { status: 400 })),
  );
  expect(await notifyAlert(event)).toEqual({
    ok: false,
    status: 'failed',
    reason: 'destination is not E.164',
  });
});

test('maps a thrown fetch to "unreachable"', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('connection refused'); }));
  expect(await notifyAlert(event)).toEqual({ ok: false, status: 'unreachable' });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `npx vitest run src/lib/notifyClient.test.ts`
Expected: FAIL — `Cannot find module './notifyClient'`.

- [ ] **Step 4: Implement `src/lib/notifyClient.ts`**

```ts
import type { AlertEvent } from './alertEngine';

export interface DeliveryResult {
  ok: boolean;
  status: string;
  reason?: string;
}

const TOKEN: string | undefined = import.meta.env.VITE_ALERT_API_TOKEN;

/** POST one alert event to the delivery service. Never throws. */
export async function notifyAlert(event: AlertEvent): Promise<DeliveryResult> {
  try {
    const res = await fetch('/api/notify', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        ...(TOKEN ? { authorization: `Bearer ${TOKEN}` } : {}),
      },
      body: JSON.stringify(event),
    });
    const payload = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (res.ok) {
      return { ok: true, status: String(payload.status ?? 'sent') };
    }
    const reason = payload.reason ?? payload.error;
    return {
      ok: false,
      status: String(payload.status ?? 'error'),
      reason: reason === undefined ? undefined : String(reason),
    };
  } catch {
    return { ok: false, status: 'unreachable' };
  }
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npx vitest run src/lib/notifyClient.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 6: Run the whole suite + build**

Run: `npm test && npm run build`
Expected: green (51 tests); build passes.

- [ ] **Step 7: Commit**

```bash
git add src/vite-env.d.ts src/lib/notifyClient.ts src/lib/notifyClient.test.ts
git commit -m "$(cat <<'EOF'
Add frontend notify client

notifyAlert() POSTs an AlertEvent to /api/notify and maps the response
to a DeliveryResult; network failure becomes { ok: false, status:
'unreachable' }. Never throws.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 7: useAlertNotifier hook

**Files:**
- Create: `src/hooks/useAlertNotifier.ts`
- Test: `src/hooks/useAlertNotifier.test.tsx`

**Interfaces:**
- Consumes: `AlertEvent` (`src/lib/alertEngine`), `notifyAlert` + `DeliveryResult` (`src/lib/notifyClient`).
- Produces:
  - `type DeliveryState = 'pending' | DeliveryResult`
  - `useAlertNotifier(events: AlertEvent[]): Record<string, DeliveryState>`

- [ ] **Step 1: Write the failing test — `src/hooks/useAlertNotifier.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/hooks/useAlertNotifier.test.tsx`
Expected: FAIL — `Cannot find module './useAlertNotifier'`.

- [ ] **Step 3: Implement `src/hooks/useAlertNotifier.ts`**

```ts
import { useEffect, useRef, useState } from 'react';
import type { AlertEvent } from '../lib/alertEngine';
import { notifyAlert, type DeliveryResult } from '../lib/notifyClient';

export type DeliveryState = 'pending' | DeliveryResult;

/**
 * Delivers HIGH/LOW alert events to the backend exactly once each and tracks
 * their per-event delivery status for display. Recovery (NORMAL) events are
 * ignored. Never throws.
 */
export function useAlertNotifier(events: AlertEvent[]): Record<string, DeliveryState> {
  const dispatched = useRef<Set<string>>(new Set());
  const [statuses, setStatuses] = useState<Record<string, DeliveryState>>({});

  useEffect(() => {
    for (const event of events) {
      if (event.transition !== 'HIGH' && event.transition !== 'LOW') continue;
      if (dispatched.current.has(event.id)) continue;
      dispatched.current.add(event.id);
      setStatuses((prev) => ({ ...prev, [event.id]: 'pending' }));
      void notifyAlert(event).then((result) => {
        setStatuses((prev) => ({ ...prev, [event.id]: result }));
      });
    }
  }, [events]);

  return statuses;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/hooks/useAlertNotifier.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the whole suite + build**

Run: `npm test && npm run build`
Expected: green (54 tests); build passes.

- [ ] **Step 6: Commit**

```bash
git add src/hooks/useAlertNotifier.ts src/hooks/useAlertNotifier.test.tsx
git commit -m "$(cat <<'EOF'
Add useAlertNotifier hook

Fires notifyAlert once per new HIGH/LOW event (ref-set dedupe), tracks
pending/resolved delivery status per event id. Ignores NORMAL events.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 8: Wire into App and show delivery status

**Files:**
- Modify: `src/App.tsx`
- Modify: `src/components/AlertLog.tsx`
- Modify: `src/App.test.tsx` (stub `fetch` so the mounted app makes no real request)

**Interfaces:**
- Consumes: `useAlertNotifier`, `DeliveryState` (Task 7).
- Produces: nothing new (UI wiring only).

- [ ] **Step 1: Stub `fetch` in `src/App.test.tsx`**

Add to the `beforeEach` in `src/App.test.tsx`, after `vi.useFakeTimers(...)`:

```ts
  vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 503 })));
```

And add to `afterEach`, before `container.remove()`:

```ts
  vi.unstubAllGlobals();
```

- [ ] **Step 2: Run `src/App.test.tsx` to confirm it still passes before the wiring change**

Run: `npx vitest run src/App.test.tsx`
Expected: PASS (1 test) — the stub is inert until the app calls `fetch`.

- [ ] **Step 3: Wire `useAlertNotifier` into `src/App.tsx`**

Add the import (alongside the other hook import):

```ts
import { useAlertNotifier } from './hooks/useAlertNotifier';
```

Immediately after `const alerts = useAlertEngine(frame, rules, recipients);` add:

```ts
  const delivery = useAlertNotifier(alerts);
```

Change the `AlertLog` element to pass the map:

```tsx
        <AlertLog alerts={alerts} unit={unit} delivery={delivery} />
```

- [ ] **Step 4: Add the delivery badge in `src/components/AlertLog.tsx`**

Replace the file with:

```tsx
import type { AlertEvent, AlertSource } from '../lib/alertEngine';
import type { DeliveryState } from '../hooks/useAlertNotifier';
import { formatTemp, type Unit } from '../lib/temperature';

interface Props {
  alerts: AlertEvent[];
  unit: Unit;
  delivery?: Record<string, DeliveryState>;
}

const SOURCE_LABEL: Record<AlertSource, string> = {
  SENSOR_1: 'Sensor 1',
  SENSOR_2: 'Sensor 2',
  AVERAGE: 'Sensor average',
};

function line(a: AlertEvent, unit: Unit): string {
  const t = new Date(a.timestamp).toLocaleTimeString();
  const what =
    a.transition === 'HIGH'
      ? 'above max'
      : a.transition === 'LOW'
        ? 'below min'
        : 'back in range';
  return `${t} — ${SOURCE_LABEL[a.source]} ${what} (${formatTemp(a.celsius, unit)})`;
}

function deliveryLabel(state: DeliveryState | undefined): string | null {
  if (!state) return null;
  if (state === 'pending') return 'sending…';
  if (state.ok) return state.status === 'logged' ? 'logged (console)' : 'sent';
  if (state.status === 'unreachable') return 'service unreachable';
  return state.reason ? `failed — ${state.reason}` : 'failed';
}

/** The visible stand-in for "a text/email would have been sent here". */
export function AlertLog({ alerts, unit, delivery }: Props) {
  return (
    <section className="panel">
      <h2>Alert activity</h2>
      {alerts.length === 0 ? (
        <p className="panel-hint">No alerts triggered yet.</p>
      ) : (
        <ul className="alert-list">
          {alerts.map((a, i) => {
            const badge = a.transition === 'NORMAL' ? null : deliveryLabel(delivery?.[a.id]);
            return (
              <li
                key={a.id}
                className={i === 0 ? 'alert-item alert-item-latest' : 'alert-item'}
              >
                <div className="alert-item-head">
                  <span className="alert-tag">
                    {a.transition === 'NORMAL' ? 'RECOVERED' : 'SIMULATED ALERT'}
                  </span>
                  <span className="alert-meta">{line(a, unit)}</span>
                </div>
                <div className="alert-item-body">
                  Would send to <strong>{a.destination}</strong>: &ldquo;
                  {a.message}&rdquo;
                </div>
                {badge && <div className="alert-item-delivery">SMS: {badge}</div>}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Run the frontend suite**

Run: `npx vitest run src/`
Expected: PASS — all frontend tests including `src/App.test.tsx`.

- [ ] **Step 6: Full verification**

Run: `npm test && npm run build && npm run lint`
Expected: green (54 tests), build passes, lint clean.

- [ ] **Step 7: Commit**

```bash
git add src/App.tsx src/components/AlertLog.tsx src/App.test.tsx
git commit -m "$(cat <<'EOF'
Wire alert delivery into the console

App runs useAlertNotifier on engine events; AlertLog shows a per-alert
SMS delivery badge (sending / sent / logged / failed / unreachable).
App.test stubs fetch so mounting makes no real request.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

### Task 9: Docs + end-to-end verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a "Running with SMS alerts" section to `README.md`**

Insert after the existing run/install instructions:

```markdown
## Running with SMS alerts

`npm run dev` starts the web app **and** a small delivery service
(`server/`, on `127.0.0.1:8787`). The browser evaluates alerts against the
mock sensor data as usual and POSTs each HIGH/LOW transition to the service.

Delivery mode is set by `server/.env` (copy from `server/.env.example`):

| `SMS_MODE` | Behaviour | Needs |
| --- | --- | --- |
| `console` (default) | Logs the message to the server console. Nothing is sent. | nothing |
| `test` | Calls the Twilio API with **test credentials** and [magic numbers](https://www.twilio.com/docs/iam/test-credentials). Exercises the real request path without sending or charging. | Twilio test SID/token; `TWILIO_FROM_NUMBER=+15005550006` |
| `live` | Sends a real SMS. | Twilio live SID/token, an SMS-capable Twilio number, and (on a trial account) a verified destination number |

Set the destination phone number in the app's **Threshold alerts** panel
(E.164 format, e.g. `+15551234567`). To test end to end in `console` mode:
open the app, use the **Demo controls** to pin a sensor above 50 °C, and
watch the server console for the `[sms:console]` line and the app's Alert
activity panel for the delivery badge.

If `ALERT_API_TOKEN` is set in `server/.env`, also set
`VITE_ALERT_API_TOKEN` (same value) in a root `.env` file so the frontend
can authenticate.
```

- [ ] **Step 2: End-to-end manual test in `console` mode**

```bash
cp server/.env.example server/.env   # SMS_MODE stays console
npm run dev
```

In the browser (Vite URL, usually `http://localhost:5173`):
1. In **Threshold alerts**, set Destination to `+15551234567`.
2. In **Demo controls**, pin Sensor 1 to `60`.
3. Confirm: the **Alert activity** panel shows a `SIMULATED ALERT … above max` row with an `SMS: logged (console)` badge, and the terminal running the `api` process prints `[sms:console] to=+15551234567 body="…"`.
4. Un-pin Sensor 1; confirm a `RECOVERED` row appears with **no** SMS badge.

Stop with Ctrl-C.

- [ ] **Step 3: Confirm the token gate (optional, quick)**

Set `ALERT_API_TOKEN=devtoken` in `server/.env`, create root `.env` with `VITE_ALERT_API_TOKEN=devtoken`, restart `npm run dev`, repeat the pin test — the badge should still reach `logged (console)`. Then blank `VITE_ALERT_API_TOKEN`, restart, pin again — the badge should read `failed — unauthorized`. Revert both `.env` changes (or leave `server/.env` at `SMS_MODE=console`, token blank).

- [ ] **Step 4: Final full verification**

Run: `npm test && npm run build && npm run lint`
Expected: 54 tests pass, build passes, lint clean.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Document running with SMS alerts

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01QLfp4q6wXF29mmWRwF8Rrd
EOF
)"
```

---

## Notes for the executor

- **Test counts** in the plan (34, 37, 44, 48, 51, 54) assume no other test files are added or removed. If your count is off by a fixed amount but every referenced test passes, that is fine — investigate only a *decrease* or a failing named test.
- **Do not import `src/` code into `server/` or vice versa.** The `AlertEvent` shape is duplicated on purpose — the server's zod schema is the wire contract.
- **`npx vitest run <path>`** runs a single file; `npm test` runs everything. Both use the same Vitest config.
- **If `tsc -b` fails on the new project reference** (`composite` complaint), add `"composite": true` + `"declaration": true` to `server/tsconfig.json`; the emitted `.d.ts`/`.tsbuildinfo` land under `node_modules/.tmp/` and `dist/` which are already gitignored — verify `git status` is clean of build output before each commit.
- **Express default-import / `req`,`res` typing**: strict mode is off repo-wide, so `any`-typed handler params are acceptable. Prefer adding `"esModuleInterop": true` to `server/tsconfig.json` over `@ts-expect-error` if the default import errors.
- The alert engine only fires while a dashboard tab is open — this is the accepted tradeoff from the spec, not a bug to fix.

## Self-review

**Spec coverage:**
- Backend `config.ts` / modes / fail-fast → Task 1 ✅
- `SmsSender` / console / twilio / factory → Tasks 2, 3 ✅
- `notify.ts` (zod, E.164, transition gate, dedupe, compose, 400/502) → Task 4 ✅
- `app.ts` (routes, JSON limit, bearer middleware, capped seen set), `main.ts` (127.0.0.1) → Task 5 ✅
- `server/tsconfig.json`, root reference, deps, scripts, Vite proxy, `.gitignore`, `.env.example` → Tasks 1, 5 ✅
- `notifyClient.ts` (+ `vite-env.d.ts` for `VITE_ALERT_API_TOKEN`) → Task 6 ✅
- `useAlertNotifier.ts` (HIGH/LOW only, dedupe, status map) → Task 7 ✅
- `App.tsx` wiring, `AlertLog.tsx` badge → Task 8 ✅
- Error-handling table (invalid / bad phone / duplicate / provider throw / unreachable / unauthorized) → Tasks 4, 5, 6, 8 ✅
- Security (127.0.0.1 bind, token-is-not-a-secret note, `.env` gitignored) → Tasks 1, 5, 9 ✅
- Testing strategy (backend unit + supertest, frontend unit, no Twilio contact) → Tasks 1–8 ✅
- README section → Task 9 ✅
- YAGNI exclusions (no multi-recipient, no retry/queue, engine stays client-side) → respected; not implemented ✅

**Placeholder scan:** No TBD/TODO/"handle errors appropriately". Every code step has literal code. Fallback branches ("if `tsc -b` complains…") give an exact alternative, not a vague direction.

**Type consistency:** `Config`, `SmsMode`, `TwilioConfig`, `SmsMessage`, `SmsResult`, `SmsSender`, `NotifyDeps` (`seen: Set<string>`), `NotifyOutcome` (`code: 200|400|502`), `AlertEventInput`, `DeliveryResult` (`{ ok, status, reason? }`), `DeliveryState` (`'pending' | DeliveryResult`) — each defined once and consumed with the same shape. `createApp` takes `{ config, sender }` in Tasks 5 and its test. `notifyAlert(event)` signature matches between Tasks 6, 7, 8. `AlertLog` prop `delivery?: Record<string, DeliveryState>` matches what Task 8 App passes.
