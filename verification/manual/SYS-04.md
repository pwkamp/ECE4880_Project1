# SYS-04 - Remote Display Response Latency

Set `THERMOMETER_UART_PORT` to the ESP32 serial port (for example `COM8`) and close ESP-IDF Monitor so the runner can open it. Keep the actual frontend at `http://127.0.0.1:5173` and the backend connected.

The runner starts Playwright against the live GUI, performs 10 alternating ON/OFF actions per sensor, and timestamps each browser click. Firmware emits `VERIFY DISPLAY_RENDER` only after applying the BLE command and calling the display renderer. The runner matches each click to the sensor/state-specific UART marker and computes the end-to-end latency. All 20 pairs must exist and every latency must be below 1000 ms. A live-GUI screenshot, Playwright log, UART event log, and paired timing records are retained automatically.

If UART capture is unavailable the test is BLOCKED. Operator reaction time, HTTP acknowledgement, backend state, or a mocked GUI is not accepted as physical-render timing evidence.
