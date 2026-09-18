// Transport-agnostic sensor bus interfaces implemented by the device HAL
// (Wire/UART on ESP32-C3) and by the host test harness (fake buses).
#pragma once
#include <cstdint>
#include <cstddef>

namespace bb {

struct I2c {
    virtual ~I2c() = default;
    // Write then read (repeated start). false on NACK/bus error.
    virtual bool write(uint8_t addr, const uint8_t* data, size_t len) = 0;
    virtual bool read(uint8_t addr, uint8_t* out, size_t len) = 0;
};

struct Uart {
    virtual ~Uart() = default;
    virtual void write(const uint8_t* data, size_t len) = 0;
    // Bytes received since last call; false if none.
    virtual int available() = 0;
    virtual uint8_t read_byte() = 0;
};

}  // namespace bb
