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
stack high-water mark. The 50 ms preferred BLE connection interval is intended
to make history transfer fast; measure its connected-idle current against the
previous 200 ms setting before treating it as a production power configuration.
The central may negotiate a different interval. Measure display actuation
against the one-second target and history recovery against the ten-second target.
The five-second connector
confirmation timeout tolerates late WinRT acknowledgements; it does not change
the display-actuation target. If peripheral latency 1 violates either measured
target, set it back to 0 in the shared JSON.
