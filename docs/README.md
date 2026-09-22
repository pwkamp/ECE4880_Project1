# Thermometer design documentation

- [`architecture.md`](architecture.md) summarizes request flow, lifecycle ownership,
  and firmware state ownership.
- [`requirements_traceability.md`](requirements_traceability.md) maps the active
  implementation to the Jira requirement and SCRUM identifiers verified read-only.
- [`power_measurement.md`](power_measurement.md) defines the hardware measurements
  still needed before final power and timing acceptance.
- [`integration-test.md`](integration-test.md) runs physical DS18B20 data
  through built-in Bluetooth, MySQL, and the React chart on Windows or Linux.

These documents cover the BLE firmware and connector backend. The web console
is in [`frontend/`](../frontend/).
