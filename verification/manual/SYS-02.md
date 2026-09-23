# SYS-02 - Full-System Sensor Disconnect and Recovery

For each sensor, test both pre-disconnection display states (ON and OFF). The runner first sets and confirms the state, then actively disconnects the computer's BLE link. While the PC is disconnected, unplug and reconnect that physical sensor without restarting the ESP32. Confirm on the physical LCD that the other sensor continues and that the recovered sensor independently returns to its pre-disconnection state. The runner then reconnects the backend and confirms the firmware-reported state. Repeat all four sensor/state combinations.

This separation is essential: backend observations alone cannot prove that state restoration is implemented locally in firmware. Any unperformed action or unavailable visual observation is BLOCKED, while an observed wrong state is FAIL.
