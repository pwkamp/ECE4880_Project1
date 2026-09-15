cmake_minimum_required(VERSION 3.22)

# The protocol is owned by the monorepo rather than either consumer. A cache
# override keeps standalone firmware builds possible, while the default
# resolves the sibling ../protocol directory used by ECE4880_Project1.
set(THERMOMETER_PROTOCOL_DIR "" CACHE PATH
    "Directory containing the shared thermometer protocol definition")
if(NOT THERMOMETER_PROTOCOL_DIR)
    set(THERMOMETER_PROTOCOL_DIR "${CMAKE_CURRENT_LIST_DIR}/../protocol")
endif()
get_filename_component(THERMOMETER_PROTOCOL_DIR
    "${THERMOMETER_PROTOCOL_DIR}" ABSOLUTE)
if(NOT IS_DIRECTORY "${THERMOMETER_PROTOCOL_DIR}")
    message(FATAL_ERROR
        "Shared protocol directory not found at ${THERMOMETER_PROTOCOL_DIR}. "
        "Keep firmware/ and protocol/ as siblings or pass "
        "-DTHERMOMETER_PROTOCOL_DIR=<path>.")
endif()
foreach(protocol_file
        thermometer_protocol.json
        shared_config.py
        generate_firmware_config.py)
    if(NOT EXISTS "${THERMOMETER_PROTOCOL_DIR}/${protocol_file}")
        message(FATAL_ERROR
            "THERMOMETER_PROTOCOL_DIR is incomplete: missing ${protocol_file} "
            "under ${THERMOMETER_PROTOCOL_DIR}")
    endif()
endforeach()

if(DEFINED IDF_TARGET AND NOT IDF_TARGET STREQUAL "esp32")
    message(FATAL_ERROR "This firmware currently supports only the original ESP32 target.")
endif()
set(IDF_TARGET "esp32" CACHE STRING "Supported ESP-IDF target")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
project(thermometer_gatt_server)

# ESP-IDF 6.1's NimBLE NVS implementation indexes the compile-time one-element
# bond array inside a loop that is unreachable at runtime. GCC 15 diagnoses the
# dead expression as an array-bounds error. Suppress only that warning for the
# upstream Bluetooth component so project warnings remain errors.
if(CMAKE_C_COMPILER_ID STREQUAL "GNU" AND
   CMAKE_C_COMPILER_VERSION VERSION_GREATER_EQUAL 15)
    idf_component_get_property(bt_component bt COMPONENT_LIB)
    target_compile_options(${bt_component} PRIVATE -Wno-error=array-bounds)
endif()
