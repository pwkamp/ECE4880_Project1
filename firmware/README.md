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

The fake/real sensor and display backends are independently selectable under
**Thermometer Configuration** in `idf.py menuconfig`. Before integrating real
hardware, build each of these combinations after changing the two selections:

| Sensor backend | Display backend | Expected purpose |
|---|---|---|
| Fake | LED | Complete simulation profile |
| Real | LED | Real-sensor testing without the LCD |
| Fake | Real | LCD/button integration with simulated temperatures |
| Real | Real | Production DS18B20, LCD, and button hardware |

There is not yet a separate on-target Unity unit-test application. Hardware
acceptance therefore requires flashing the default build, connecting through
the backend service or GUI, confirming secure connection and 1 Hz readings,
synchronizing history, controlling both display states, and power-cycling the
board to verify automatic reconnection. These checks require the actual ESP32
and cannot be run by `master_test.py`.

Production builds default to the two real DS18B20 buses and the real HD44780
LCD/button backend. The LCD uses RS/E/D4/D5/D6/D7 on GPIO16/17/18/19/21/23;
the active-low sensor buttons use GPIO34/GPIO35 with external pull-ups. LCD or
button initialization errors are logged but do not prevent sensor sampling or
BLE startup. The fake sensors and LED simulator remain available through
`menuconfig` for isolated development builds.

## Full cross-platform integration

The firmware itself stays on the ESP32 and is built/flashed from the native
Windows or Linux host. MySQL and the web application are containerized on both
platforms; the BLE backend is native on Windows and containerized with host
BlueZ access on Linux. Keep the production **Two DS18B20 sensors** and
**HD44780 LCD and physical sensor buttons** selections, set the six-digit PIN
in `device_config.cmake`, and flash before starting the backend:

```bash
idf.py set-target esp32
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

After the board advertises as `Thermometer-XXXXXX`, follow
[`docs/integration-test.md`](../docs/integration-test.md) to start the three
components and verify the complete BLE-to-graph path using the PC's built-in
Bluetooth adapter.
