set(SHARED_CONFIG "${THERMOMETER_PROTOCOL_DIR}/thermometer_protocol.json")
set(CONFIG_GENERATOR "${THERMOMETER_PROTOCOL_DIR}/generate_firmware_config.py")
set(CONFIG_VALIDATOR "${THERMOMETER_PROTOCOL_DIR}/shared_config.py")
set(GENERATED_CONFIG "${CMAKE_BINARY_DIR}/generated/thermometer_config.h")
set(DEVICE_CONFIG "${CMAKE_CURRENT_LIST_DIR}/../device_config.cmake")
# ESP-IDF validates INCLUDE_DIRS while configuring, before the custom command
# below generates the first header in this directory.
file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/generated")

# A command-line value overrides the local, gitignored per-device file.
set(HAS_PAIRING_PASSKEY_OVERRIDE FALSE)
if(DEFINED CACHE{THERMOMETER_PAIRING_PASSKEY})
    set(HAS_PAIRING_PASSKEY_OVERRIDE TRUE)
    set(PAIRING_PASSKEY_OVERRIDE "$CACHE{THERMOMETER_PAIRING_PASSKEY}")
endif()
if(EXISTS "${DEVICE_CONFIG}")
    include("${DEVICE_CONFIG}")
endif()
if(HAS_PAIRING_PASSKEY_OVERRIDE)
    set(THERMOMETER_PAIRING_PASSKEY "${PAIRING_PASSKEY_OVERRIDE}")
endif()
if(NOT DEFINED THERMOMETER_PAIRING_PASSKEY OR
   NOT THERMOMETER_PAIRING_PASSKEY MATCHES "^[0-9][0-9][0-9][0-9][0-9][0-9]$")
    message(FATAL_ERROR
        "THERMOMETER_PAIRING_PASSKEY must contain exactly six digits. Copy "
        "device_config.cmake.example to device_config.cmake or pass "
        "-DTHERMOMETER_PAIRING_PASSKEY=<six-digits>.")
endif()

set(SENSOR_BACKEND_SOURCE "src/fake_temperature_sensors.c")
if(CONFIG_THERMOMETER_SENSOR_BACKEND_REAL)
    set(SENSOR_BACKEND_SOURCE "src/real_temperature_sensors.c")
endif()

set(DISPLAY_BACKEND_SOURCE "src/led_display.c")
if(CONFIG_THERMOMETER_DISPLAY_BACKEND_REAL)
    set(DISPLAY_BACKEND_SOURCE "src/real_display.c")
endif()

idf_component_register(
    SRCS
        "main.c"
        "src/application_auth.c"
        "src/ble_server.c"
        "src/history_buffer.c"
        "src/local_controls.c"
        "src/protocol.c"
        "src/thermometer.c"
        "${SENSOR_BACKEND_SOURCE}"
        "${DISPLAY_BACKEND_SOURCE}"
    PRIV_REQUIRES bt nvs_flash esp_driver_gpio esp_pm esp_system esp_timer mbedtls
    INCLUDE_DIRS "include" "${CMAKE_BINARY_DIR}/generated"
)

# Component requirement discovery evaluates this file in CMake script mode,
# where build rules cannot be declared.
if(NOT CMAKE_BUILD_EARLY_EXPANSION)
    idf_build_get_property(PYTHON_EXECUTABLE PYTHON)
    set(CONFIG_DEPENDENCIES
        "${SHARED_CONFIG}"
        "${CONFIG_GENERATOR}"
        "${CONFIG_VALIDATOR}"
    )
    if(EXISTS "${DEVICE_CONFIG}")
        list(APPEND CONFIG_DEPENDENCIES "${DEVICE_CONFIG}")
    endif()
    add_custom_command(
        OUTPUT "${GENERATED_CONFIG}"
        COMMAND "${PYTHON_EXECUTABLE}" "${CONFIG_GENERATOR}"
                --input "${SHARED_CONFIG}"
                --output "${GENERATED_CONFIG}"
                --pairing-passkey "${THERMOMETER_PAIRING_PASSKEY}"
        DEPENDS ${CONFIG_DEPENDENCIES}
        COMMENT "Generating shared thermometer protocol header"
        VERBATIM
    )
    add_custom_target(generate_thermometer_config DEPENDS "${GENERATED_CONFIG}")
    add_dependencies(${COMPONENT_LIB} generate_thermometer_config)
endif()
