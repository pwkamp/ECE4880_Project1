# Architecture

## Request path

The PC is the only application requester. A BLE operation is one serialized
GATT write followed by its matching GATT read. The firmware never sends
application notifications or indications.

`ThermometerBleService` is the public facade. Its lifecycle manager owns device
selection and reconnection, `BleRequestScheduler` orders display/current/history
traffic, and `PersistenceWorker` keeps database latency out of the radio timing
path. `ThermometerBleClient` performs only pairing, connection, authentication,
and primitive protocol exchanges; it never retries or reconnects on its own.

## Lifecycle

Lifecycle inputs are queued as typed events. Entering `DISCOVERING` or
`RECONNECTING` always starts a bounded scan, so neither state depends on an HTTP
status request or a manual scan to advance. Every scan and connection attempt is
tagged with the current attempt generation; results from superseded attempts are
discarded.

`connected` means that a GATT transport is open. `ready` additionally requires
service discovery, authenticated BLE security, application challenge-response,
protocol-version verification, and a successful initial current snapshot.

## Firmware ownership

`ble_server.c` owns GAP/GATT lifecycle. `protocol.c` validates and dispatches
wire packets. `application_auth.c` owns challenge expiry, lockout, and proof
verification. `history_buffer.c` implements the fixed circular buffers.
`thermometer.c` is the sole owner of live sensor state, display state, history
insertion, and atomic snapshots.

Each sensor task waits for its next conversion and posts the result to the state
task. A one-second state-task deadline records the latest independent sensor
values into both history rings and refreshes the display. No ISR or timer
callback performs sensor I/O, display I/O, BLE work, or packet processing.
