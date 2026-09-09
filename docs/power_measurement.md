# Power measurement checklist

The production defaults enable BLE modem sleep, dynamic frequency scaling,
tickless idle, size optimization, warning-level logs, one connection, and no
notifications or indications. Automatic light sleep remains disabled because
the supported original ESP32 uses the main crystal as the Bluetooth low-power
clock.

Before reducing task stacks or protocol buffers, capture these measurements with
the intended sensors and display attached:

| Mode | Record |
|---|---|
| Advertising with no client | Average and peak current |
| Connected and between polls | Average and peak current |
| One-second current polling | Average and peak current |
| History synchronization | Average current and completion time |
| Display enabled/disabled | Current delta and command latency |

In a diagnostic build also record minimum free heap and each application task's
stack high-water mark. Keep the 0.9-second display response and ten-second
recovery/history budgets as hard constraints. If peripheral latency 1 violates
either limit in hardware testing, set it back to 0 in the shared JSON.
