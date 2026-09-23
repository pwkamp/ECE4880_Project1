# BLE-02 — Authenticated Display Control

Using a real ESP32, run an authorized SET_DISPLAY command and verify the physical LCD. From an unbonded/unauthenticated client, attempt state-changing access and verify rejection. Send malformed sensor IDs, values, lengths, and protocol versions and verify defined error status with no LCD state change. Preserve BLE/serial traces; a backend acknowledgement alone is insufficient.
