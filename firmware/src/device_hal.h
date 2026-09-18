// Device HAL: ESP32-C3 (Arduino framework) implementations of the core
// bus/clock interfaces. Compiled ONLY for the esp32c3 env (platformio.ini
// excludes this file from the native test build; guarded again by
// NATIVE_TEST for safety). Pin map is defined by the schematic net names
// (hardware/kicad/generate_schematic.py U1 controller_nets):
//   I2C_SDA  -> GPIO4  (module pin 3)
//   I2C_SCL  -> GPIO5  (module pin 4)
//   PM_ENABLE-> GPIO6  (module pin 5)  -> U7 TPS22919 ON (active-high)
//   STATUS_LED_K -> GPIO7 (module pin 6) active-low
//   USER_BUTTON_N -> GPIO10 (module pin 10, internal state via R8 pull-up)
//   PM_UART_TX -> GPIO20_U0TXD (module pin 11)
//   PM_UART_RX -> GPIO21_U0RXD (module pin 12)
//   CC1_SENSE -> GPIO0 (module pin 18), CC2_SENSE -> GPIO1 (module pin 17)
//   REG_PG -> GPIO3 (module pin 15)
// The module USB pins (18/19 = GPIO18/19) are the native USB port (J1 via
// series R11/R12), not touched here.
//
// NOTE on the UART assignment: PM_UART_* ride the U0 console pins, so the
// SPS30 SHDLC traffic and the USB-serial fallback protocol share pin
// functions only when USB CDC is off; the baseline build uses USB CDC for
// the serial protocol (USB_DM/D+) and this UART strictly for the SPS30.
#pragma once
#if !defined(NATIVE_TEST)
#include <Arduino.h>
#include <Wire.h>

#include "core/hal.h"

namespace bb::device {

class ArduClock : public Clock {
public:
    uint64_t monotonic_us() override { return micros(); }
    void delay_ms(uint32_t ms) override { ::delay(ms); }
};

class ArduI2c : public I2c {
public:
    void begin() { Wire.begin(/*SDA=*/4, /*SCL=*/5, 100000); }  // 100 kHz std mode (SHT40/SGP40 §4)
    bool write(uint8_t addr, const uint8_t* data, size_t len) override {
        Wire.beginTransmission(addr);
        Wire.write(data, len);
        return Wire.endTransmission() == 0;
    }
    bool read(uint8_t addr, uint8_t* out, size_t len) override {
        Wire.requestFrom(addr, static_cast<int>(len));
        size_t i = 0;
        while (Wire.available() && i < len) out[i++] = static_cast<uint8_t>(Wire.read());
        return i == len;
    }
};

class ArduUart : public Uart {
public:
    void begin() { Serial1.begin(115200, SERIAL_8N1, /*RX=*/21, /*TX=*/20); }
    void write(const uint8_t* data, size_t len) override { Serial1.write(data, len); }
    int available() override { return Serial1.available(); }
    uint8_t read_byte() override { return static_cast<uint8_t>(Serial1.read()); }
};

}  // namespace bb::device
#endif  // !NATIVE_TEST
