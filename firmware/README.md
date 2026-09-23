# ESP32 thermometer firmware

This directory is a complete ESP-IDF project for the original ESP32. It
consumes the repository-level `../protocol` definition and generates its C
configuration header during the build.

When working from the complete monorepo, open
`../ECE4880_Project1.code-workspace` and select `firmware` using
**ESP-IDF: Pick a Workspace Folder**. The committed `.vscode/settings.json`
keeps the build directory, `sdkconfig`, compile database, and IDF target scoped
to this firmware project. Opening this directory directly also works.

## Configure and build

Use ESP-IDF 6.x. From this directory in an initialized ESP-IDF terminal:

```powershell
if (-not (Test-Path device_config.cmake)) {
    Copy-Item device_config.cmake.example device_config.cmake
}
# Set a unique six-digit passkey in device_config.cmake.
idf.py --no-ccache build
```

The local `device_config.cmake`, generated `sdkconfig`, build directory, and
firmware binaries are ignored by the repository. Commit
`device_config.cmake.example` and the two `sdkconfig.defaults` files instead.

History recovery now freezes a copy of both 300-record rings when the backend
requests history metadata. Rebuild and reflash after updating this firmware;
an ESP32 still running the earlier firmware may return `NOT_AVAILABLE` for the
oldest record while its live ring advances, leaving history recovery at 0%.
This revision also adds a compact history response and requests a 50 ms BLE
connection interval. Reflash before measuring the 300-second recovery time.
The normal ESP-IDF build and the VS Code Build button both use `build/`.
The VS Code configuration disables `ccache`; use `--no-ccache` for the same
behavior in an ESP-IDF terminal on this Windows setup.
After moving this repository from another checkout, old generated compiler
flags can contain two `picolibc.specs` paths and fail with a duplicate-spec
error. In that case, back up or clean only the generated `build/` directory
once, then run the normal build again. Do not edit `toolchain/cflags` by hand.

Flash and monitor the board with the appropriate port:

```powershell
idf.py -p COM5 flash monitor
```

Replace `COM5` with the ESP32's actual serial port.

## Firmware tests

The active automated firmware check is a clean ESP-IDF production build. It
validates the shared JSON, regenerates `build/generated/thermometer_config.h`,
compiles all selected firmware modules, links the application, and checks the
partition size:

```powershell
idf.py --no-ccache build
idf.py size
```

The physical/test temperature sensor backend remains selectable under
**Thermometer Configuration** in `idf.py menuconfig`. Production builds default
to the two physical DS18B20 probes; simulated readings require explicitly
selecting **Deterministic simulated sensors**.

The local hardware copied from the prototype firmware is wired as follows:

| Function | ESP32 GPIO |
|---|---:|
| Sensor 1 DS18B20 data | 14 |
| Sensor 2 DS18B20 data | 27 |
| LCD RS | 16 |
| LCD Enable | 17 |
| LCD D4, D5, D6, D7 | 18, 19, 21, 23 |
| Sensor 1 button | 34 |
| Sensor 2 button | 35 |

The buttons are active-low and use 40 ms software debounce. GPIO34 and GPIO35
do not provide internal pull-ups, so each button input requires an external
pull-up resistor and the switch must connect the input to ground when pressed.
Each DS18B20 uses its own three-wire bus and requires an approximately 4.7 kOhm
pull-up from data to 3.3 V. Parasitic-power wiring is not supported. With no
valid presence pulse, or with a bad scratchpad CRC, that sensor is reported as
disconnected and cannot be switched to the display's ON state.

If a Windows/BlueZ bond becomes stale, the current firmware permits an
explicitly reset host to replace the stored ESP32 peer bond, but only by
completing authenticated pairing with the configured six-digit PIN. Use the
backend launcher's `-ResetPairings`/`--reset-pairings` option; normal reconnects
continue to reuse the existing bond.
The LCD backlight is powered directly; the current hardware has no backlight
control pin. The prototype's GPIO32/GPIO33 sensor LEDs are intentionally not
used by this firmware.

There is not yet a separate on-target Unity unit-test application. Hardware
acceptance therefore requires flashing the default build, connecting through
the backend service or GUI, confirming secure connection and 1 Hz readings,
synchronizing history, controlling both display states, and power-cycling the
board to verify automatic reconnection. These checks require the actual ESP32
and cannot be run by `master_test.py`.

The DS18B20 sensors, HD44780 LCD, and two physical buttons are the default
production configuration. The deterministic backend remains available only
for explicit simulation testing. LCD or button initialization errors are
logged but do not prevent sensor sampling or BLE startup.

## Flashing without holding BOOT

No application-firmware change is needed or able to control entry into the
original ESP32 ROM download mode. ESP-IDF already asks the serial adapter to
toggle DTR/RTS so a development board with the standard auto-reset circuit can
enter download mode and flash without pressing **BOOT**. Use the normal VS Code
**Flash** button or `idf.py -p COM5 flash`.

If flashing only connects while **BOOT** is held, the board or USB-to-serial
adapter does not expose a working automatic EN/GPIO0 reset circuit. Use the
correct USB-UART driver and a data-capable cable; otherwise the remedy is a
board/adapter with automatic DTR/RTS wiring (or adding that hardware circuit),
not a change to this firmware.

## Full cross-platform integration

The firmware itself stays on the ESP32 and is built/flashed from the native
Windows or Linux host. MySQL and the web application are containerized on both
platforms; the BLE backend is native on Windows and containerized with host
BlueZ access on Linux. Keep the default **Two DS18B20 sensors on
GPIO14/GPIO27** selection, set the six-digit PIN in `device_config.cmake`, and
flash before starting the backend:

```bash
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

After the board advertises as `Thermometer-XXXXXX`, follow the root
[`README.md`](../README.md#connecting-the-console-to-ble-and-mysql) to start
the three components and verify the complete BLE-to-graph path using the PC's
built-in Bluetooth adapter.
