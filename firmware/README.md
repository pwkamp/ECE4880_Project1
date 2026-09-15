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
idf.py set-target esp32
idf.py build
```

The local `device_config.cmake`, generated `sdkconfig`, build directory, and
firmware binaries are ignored by the repository. Commit
`device_config.cmake.example` and the two `sdkconfig.defaults` files instead.

Flash and monitor the board with the appropriate port:

```powershell
idf.py -p COM5 flash monitor
```

## Firmware tests

The active automated firmware check is a clean ESP-IDF production build. It
validates the shared JSON, regenerates `build/generated/thermometer_config.h`,
compiles all selected firmware modules, links the application, and checks the
partition size:

```powershell
idf.py fullclean
idf.py build
idf.py size
```

The fake/real sensor and display backends are independently selectable under
**Thermometer Configuration** in `idf.py menuconfig`. Before integrating real
hardware, build each of these combinations after changing the two selections:

| Sensor backend | Display backend | Expected purpose |
|---|---|---|
| Fake | LED | Complete default simulation |
| Real | LED | Compile-check sensor integration stub |
| Fake | Real | Compile-check display integration stub |
| Real | Real | Compile-check both hardware integration stubs |

There is not yet a separate on-target Unity unit-test application. Hardware
acceptance therefore requires flashing the default build, connecting through
the backend service or GUI, confirming secure connection and 1 Hz readings,
synchronizing history, controlling both display states, and power-cycling the
board to verify automatic reconnection. These checks require the actual ESP32
and cannot be run by `master_test.py`.

Real sensor and display files are integration stubs; fake sensors and the LED
display simulator are the default working backends.
