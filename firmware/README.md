# Firmware Plan

## Responsibilities
- Initialize sensors and validate readiness states
- Execute deterministic sampling loop and timestamp records
- Persist bounded local history and configuration
- Expose local protocol endpoints for companion app
- Handle calibration/baseline workflows and reset/recovery actions

## Interfaces
- Sensor buses: I2C and optional UART for PM sensor module
- Local transport: Wi-Fi local API + USB serial fallback
- Status/input: button events and indicator states

## Provisioning and update approach
- Initial provisioning via serial or temporary setup mode
- Versioned configuration schema for safe upgrades
- Documented firmware flashing and rollback path

## Test strategy
- Build reproducibility in CI/local toolchain
- Unit tests for parsing, averaging, event markers, and retention rollover
- Hardware-in-loop smoke checks for sensor communication
- Protocol compatibility checks with companion app contract
