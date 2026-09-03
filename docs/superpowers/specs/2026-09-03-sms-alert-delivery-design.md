# SMS Alert Delivery — Design

**Date:** 2026-09-03
**Status:** Approved for planning
**Related Jira:** SCRUM-621..624, SCRUM-633 (alert engine, already implemented); SCRUM-628 (session cookie protection, adjacent)

## Problem

The console currently evaluates temperature alerts entirely in the browser
(`useAlertEngine` → `stepAlertEngine`) and only *simulates* delivery — the
"Alert activity" panel renders `Would send to <destination>: "<message>"` and
nothing is actually sent. We want a real backend service that sends an SMS to a
phone number when an alert fires, while still driving the whole thing from the
existing fake sensor data so it can be tested without hardware.

## Goals

- A real SMS is delivered on a genuine alert excursion (`NORMAL→HIGH`,
  `NORMAL→LOW`).
- The existing client-side engine, mock data source, and React code are reused
  unchanged in behaviour — the browser POSTs fired events to the new service.
- Safe by default: no message is sent and no provider account is required until
  someone explicitly opts in.
- Every existing test stays green; new code is covered.

## Non-goals (YAGNI)

- Multi-recipient UI or per-recipient rule configuration beyond today's single
  free-text destination.
- Delivery queue, retry, or persistence — an in-memory dedupe set is enough.
- Moving the alert state machine server-side (alerts only fire while a dashboard
  tab is open; acceptable for this tool).
- A real authentication system.
- Production/deploy configuration for the backend.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| SMS provider | **Twilio** | Free trial, test credentials + magic numbers that exercise the real SDK/request path without sending or charging, best docs. |
| Engine location | **Stays client-side**; backend only delivers | Smallest change; reuses all existing tested code. Tradeoff accepted: alerts fire only while a dashboard tab is open. |
| Test safety | **Three modes** via `SMS_MODE`: `console` (log only, default) / `test` (Twilio test creds + magic numbers) / `live` (real send) | Safe by default, explicit opt-in to spend, provider integration still testable. |
| Recipients | **Reuse the single Destination field** in the Threshold alerts panel; backend validates E.164 | One recipient is all the UI models today. |
| Backend framework | **Express** + `tsx` in dev | Ubiquitous, minimal, matches the "Node/TypeScript" framing and the SCRUM tickets that reference `express-session`. |
| Which transitions send SMS | **`HIGH` and `LOW` only** | Recovery (`→NORMAL`) still shows in the Alert activity log but sends no text — avoids double-texting every blip. |
| Dev workflow | **One command** — `npm run dev` runs Vite + backend via `concurrently`; Vite proxies `/api` → backend | One terminal; secrets in `server/.env`. |

## Architecture

```
Browser (unchanged behaviour)                       New service: server/  (Express, 127.0.0.1:8787)
─────────────────────────────                       ────────────────────────────────────────────────
MockThermometerSource → useThermometer → frame
        │
useAlertEngine(frame, rules, recipients)
        │  stepAlertEngine → AlertEvent[]
        ├──────────────▶ AlertLog  (now also renders a delivery badge)
        │
        └─ useAlertNotifier(events)
              for each NEW event, transition ∈ {HIGH, LOW}:
                 notifyAlert(event)
                 → POST /api/notify   ──Vite proxy──▶   POST /api/notify
                                                          1. optional Bearer-token check
                                                          2. zod-validate AlertEvent body
                                                          3. E.164-validate event.destination
                                                          4. dedupe on event.id (capped Set)
                                                          5. compose SMS text
                                                          6. SmsSender.send({ to, body })
                                                               console → console.log      → { status: 'logged' }
                                                               test    → twilio (test)     → { status: 'sent', providerId }
                                                               live    → twilio (live)     → { status: 'sent', providerId }
                                                          7. 200 { status, providerId? } | 400 | 401 | 502
              ← response updates per-event delivery status in the hook's state
```

## Components

### Backend — `server/`

#### `server/config.ts`
Reads and validates `process.env` exactly once, exports a frozen `Config`.

- `mode: 'console' | 'test' | 'live'` — from `SMS_MODE`, default `console`.
- `port: number` — from `PORT`, default `8787`.
- `apiToken: string | null` — from `ALERT_API_TOKEN`, default `null` (no check).
- `twilio: { accountSid, authToken, fromNumber } | null` — populated only when
  present.
- On load: if `mode` is `test` or `live` and any Twilio field is missing, throw
  a descriptive `Error` (this aborts `main.ts` startup). `console` mode needs
  no Twilio config.
- Pure and synchronous; unit-tested by passing a fake `env` record.

#### `server/sms/types.ts`
```ts
export interface SmsMessage { to: string; body: string; }
export interface SmsResult {
  status: 'sent' | 'logged';
  providerId?: string;
}
export interface SmsSender {
  send(msg: SmsMessage): Promise<SmsResult>;   // throws on provider failure
}
```

#### `server/sms/consoleSender.ts`
Logs `[sms:console] to=<to> body=<body>` and returns `{ status: 'logged' }`.
No dependencies.

#### `server/sms/twilioSender.ts`
Constructs a `twilio(accountSid, authToken)` client from `Config.twilio`.
`send()` calls `client.messages.create({ to, from, body })`, returns
`{ status: 'sent', providerId: message.sid }`. Any SDK rejection propagates
(the route maps it to 502). Used for **both** `test` and `live` — the only
difference is which credentials `config.ts` supplied.

#### `server/sms/index.ts`
```ts
export function createSmsSender(config: Config): SmsSender
```
`console` → `consoleSender`; `test` / `live` → `new TwilioSender(config.twilio!)`.

#### `server/notify.ts`
The delivery decision, framework-free so it is unit-testable without HTTP.

```ts
interface NotifyDeps {
  sender: SmsSender;
  seen: Set<string>;      // event ids already processed (caller owns/caps it)
  now?: () => number;
}
interface NotifyOutcome {
  code: 200 | 400 | 502;
  payload: Record<string, unknown>;
}
export async function handleNotify(rawBody: unknown, deps: NotifyDeps): Promise<NotifyOutcome>
```

Steps:
1. `AlertEventSchema` (zod) parses `rawBody`. Failure → `400 { error: 'invalid event', detail }`.
2. `transition` must be `HIGH` or `LOW` → otherwise `400 { error: 'not a deliverable transition' }`.
   (The client already filters; this is defence in depth.)
3. `destination` must match E.164 (`/^\+[1-9]\d{1,14}$/`) → else `400 { error: 'destination is not E.164' }`.
4. If `deps.seen.has(event.id)` → `200 { status: 'skipped', reason: 'duplicate' }`.
5. Compose body: `` `${event.message} (${sourceLabel(event.source)} ${event.celsius.toFixed(1)}°C)` `` truncated to 320 chars (2 SMS segments max).
6. `await deps.sender.send({ to: event.destination, body })`.
   - resolves → `deps.seen.add(event.id)`; `200 { status: result.status, providerId? }`.
   - throws → `502 { status: 'failed', reason: String(err.message) }` (id **not** added, but see "no retry" — the client does not retry either).

#### `server/app.ts`
```ts
export function createApp(deps: { config: Config; sender: SmsSender }): express.Express
```
- `express.json({ limit: '16kb' })`.
- If `config.apiToken`, a middleware on `/api/notify` requiring
  `Authorization: Bearer <token>` → else `401 { error: 'unauthorized' }`.
- `POST /api/notify` → `handleNotify(req.body, { sender, seen })` where `seen`
  is a module-level `Set` capped at 5 000 ids (FIFO evict).
- `GET /api/health` → `200 { mode: config.mode }`.
- No `.listen` here so `supertest` can drive the app directly.

#### `server/main.ts`
```ts
const config = loadConfig(process.env);
const sender = createSmsSender(config);
createApp({ config, sender }).listen(config.port, '127.0.0.1',
  () => console.log(`[alert-service] ${config.mode} mode on :${config.port}`));
```

#### `server/tsconfig.json`
Node-targeted config (`module: nodenext`, `types: ["node"]`, `lib: ["ES2023"]`,
same strictness flags as the rest of the repo). Added to the root
`tsconfig.json` `references` so `tsc -b` typechecks it. Vitest discovers
`server/**/*.test.ts` with no extra config.

#### `server/.env.example`
```
# console | test | live   (default: console)
SMS_MODE=console
PORT=8787

# Required for SMS_MODE=test or live.
# test  -> use the Twilio "Test credentials" SID/token; no real number needed
# live  -> live SID/token + an SMS-capable Twilio number
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=

# Optional speed-bump. If set, the frontend must send it as VITE_ALERT_API_TOKEN.
# NOTE: this ends up in the client bundle; it is not a real secret. The service
# binding to 127.0.0.1 is the actual access control.
ALERT_API_TOKEN=
```

### Frontend — `src/`

#### `src/lib/notifyClient.ts`
```ts
export interface DeliveryResult { ok: boolean; status: string; reason?: string; }
export async function notifyAlert(event: AlertEvent): Promise<DeliveryResult>
```
`POST /api/notify` with the event as JSON, `Authorization` header from
`import.meta.env.VITE_ALERT_API_TOKEN` when defined. Maps: 2xx → `{ ok:true,
status }`; non-2xx → `{ ok:false, status: payload.status ?? 'error',
reason: payload.reason ?? payload.error }`; thrown/network error →
`{ ok:false, status: 'unreachable' }`. No React import.

#### `src/hooks/useAlertNotifier.ts`
```ts
export type DeliveryState = 'pending' | DeliveryResult;
export function useAlertNotifier(events: AlertEvent[]): Record<string, DeliveryState>
```
- Keeps a `useRef<Set<string>>` of event ids already dispatched.
- On `events` change: for each event with `transition === 'HIGH' | 'LOW'` and id
  not in the set — add it, set map entry `'pending'`, call `notifyAlert(event)`,
  then write the resolved `DeliveryResult` into the map.
- Recovery / `NORMAL` events are ignored entirely.
- Returns the status map for display. Never throws.

#### `src/App.tsx`
Add `const delivery = useAlertNotifier(alerts);` and pass `delivery` to
`<AlertLog>`.

#### `src/components/AlertLog.tsx`
New optional prop `delivery?: Record<string, DeliveryState>`. For a `HIGH`/`LOW`
row, render a badge from `delivery[a.id]`:
`pending…` / `sent` / `logged (console)` / `failed — <reason>` /
`service unreachable`. `NORMAL` rows render no badge (unchanged).

### Tooling

#### `package.json`
- `dependencies`: `express`, `twilio`, `zod`.
- `devDependencies`: `tsx`, `concurrently`, `supertest`, `@types/express`,
  `@types/supertest`.
- `scripts`:
  - `dev`: `concurrently -n web,api "vite" "npm:dev:server"`
  - `dev:server`: `tsx watch server/main.ts`
  - `test`: `vitest run` (unchanged; now also runs `server/`)
  - `build`: `tsc -b && vite build` (unchanged; `tsc -b` now also typechecks
    `server/` via the new project reference)

#### `vite.config.ts`
```ts
server: { proxy: { '/api': 'http://localhost:8787' } }
```

#### `.gitignore`
Add `server/.env`. (`*.local` already covered; `.env` is not, so add it
explicitly.)

#### `README.md`
Short "Running with SMS alerts" section: default `console` mode needs nothing;
`test` mode setup with Twilio magic numbers; `live` mode caveats.

## Data flow — the POST body

The client sends the `AlertEvent` verbatim (it already contains `destination`,
`message`, `celsius`, `source`, `transition`, `timestamp`, `id`). The server
does **not** trust it blindly — zod shape check + E.164 check + transition check
before anything is sent. `recipientId`/`ruleId` are accepted but unused by the
service today.

## Error handling

| Situation | Response | UI |
|---|---|---|
| Malformed body / missing field | `400 invalid event` | `failed — invalid event` |
| `destination` not E.164 | `400 destination is not E.164` | `failed — destination is not E.164` |
| Non-`HIGH`/`LOW` transition reached server | `400 not a deliverable transition` | (client never sends these) |
| Duplicate `event.id` | `200 { status: 'skipped' }` | badge unchanged |
| Twilio rejects / times out | `502 { status: 'failed', reason }` | `failed — <reason>` |
| Backend not running | client catch | `service unreachable` |
| Missing `Authorization` when token set | `401 unauthorized` | `failed — unauthorized` |

**No retries anywhere.** The engine is edge-triggered, so a missed excursion
text is tolerable, and retry logic risks message floods and cost. Failures are
visible in the log; the engine and the Alert activity list are never blocked by
delivery.

**Startup:** `SMS_MODE=test|live` with incomplete Twilio config → `main.ts`
throws before `listen`, printing which variable is missing.

## Security

- The service listens on **`127.0.0.1` only** — not reachable from other
  machines. This is the real access control.
- `ALERT_API_TOKEN` is an optional bearer check. Because the frontend needs it
  (`VITE_ALERT_API_TOKEN`), it is compiled into the client bundle and is **not a
  real secret** — it only stops casual same-machine curling. Documented as such.
- Twilio credentials live in `server/.env` (gitignored); `.env.example` is
  committed.
- `live` mode logs the destination number at info level; no message body content
  is logged in `live` mode.
- This is separate from SCRUM-628 (session cookies); no session/cookie layer is
  introduced here.

## Testing

### Backend (vitest, `server/**/*.test.ts`)
- `config.test.ts`: `console` default; `test`/`live` throws without Twilio vars;
  valid `live` config parses; `PORT`/`ALERT_API_TOKEN` overrides.
- `sms/consoleSender.test.ts`: returns `logged`, logs once.
- `notify.test.ts` (fake `SmsSender`, fresh `Set`):
  - valid `HIGH` event → sender called with composed body → `200 sent`.
  - valid `LOW` event → `200`.
  - bad phone (`5551234`) → `400`, sender not called.
  - missing `message` → `400`.
  - same `event.id` twice → second is `200 skipped`, sender called once.
  - sender throws → `502 failed`.
- `app.test.ts` (`supertest`, fake sender):
  - `POST /api/notify` happy path → 200.
  - with `apiToken` set: no header → 401; correct header → 200.
  - `GET /api/health` → 200 `{ mode }`.

### Frontend (vitest + jsdom)
- `notifyClient.test.ts` (`vi.stubGlobal('fetch', …)`): 2xx → `ok:true`;
  400 body → `ok:false` with reason; `fetch` rejects → `status:'unreachable'`.
- `useAlertNotifier.test.ts`: renders with a `HIGH` event → `fetch` called once;
  re-render with same event → not called again; a `NORMAL` event → never called;
  resolved result lands in the returned map.

### Not automated
No test contacts Twilio. `test` mode with magic numbers is a manual step in the
README. All 29 existing tests remain unchanged and green.

## File summary

**New**
- `server/config.ts`, `server/config.test.ts`
- `server/sms/types.ts`, `server/sms/consoleSender.ts`,
  `server/sms/consoleSender.test.ts`, `server/sms/twilioSender.ts`,
  `server/sms/index.ts`
- `server/notify.ts`, `server/notify.test.ts`
- `server/app.ts`, `server/app.test.ts`
- `server/main.ts`
- `server/tsconfig.json`
- `server/.env.example`
- `src/lib/notifyClient.ts`, `src/lib/notifyClient.test.ts`
- `src/hooks/useAlertNotifier.ts`, `src/hooks/useAlertNotifier.test.ts`

**Changed**
- `src/App.tsx` — wire `useAlertNotifier`, pass delivery map down
- `src/components/AlertLog.tsx` — delivery badge for HIGH/LOW rows
- `package.json` — deps + scripts
- `vite.config.ts` — `/api` proxy
- `tsconfig.json` — reference `server/tsconfig.json`
- `.gitignore` — `server/.env`
- `README.md` — "Running with SMS alerts"
