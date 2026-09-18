// SHT40-AD1B-R2 (U4) command layer. Datasheet: Sensirion SHT4x v6.4 (Nov 2023).
// Everything here is bus-agnostic: feed raw bytes, get decoded values.
// I2C address 0x44 is fixed by the "-A" order-code nomenclature (datasheet
// §2/Figure 18; project component-selection.md cross-check).
#pragma once
#include <cstdint>

#include "core/crc8_sensirion.h"
#include "core/sample.h"

namespace bb {

// Command bytes (Table 8). MVP baseline path uses high-repeatability (0xFD).
namespace sht40_cmd {
inline constexpr uint8_t MeasureHighRepNoStretch = 0xFD;  // §4.5, resp 6 B incl CRC
inline constexpr uint8_t SoftReset = 0x94;                // §4.5
inline constexpr uint8_t ReadSerial = 0x89;               // §4.5, resp 6 B incl CRC
}  // namespace sht40_cmd

inline constexpr uint8_t kSht40Address = 0x44;  // "-A" variant

struct Sht40Reading {
    float temp_c;
    float rh_pct;
};

enum class Sht40Error : uint8_t { Ok = 0, BadLength, CrcMismatch };

// Decode a 6-byte response [T msb, T lsb, crc, RH msb, RH lsb, crc].
// Conversion formulas: SHT4x datasheet §4.6, equations (1)/(2):
//   T = -45 + 175 * St/65535 °C        RH = -6 + 125 * Srh/65535 %RH, clamped 0..100
Sht40Error sht40_decode_measurement(const uint8_t resp[6], Sht40Reading& out);

// Convert raw ticks to engineering units (exposed for tests against the
// datasheet worked example in §4.6 pseudocode listing).
Sht40Reading sht40_ticks_to_reading(uint16_t t_ticks, uint16_t rh_ticks);

}  // namespace bb
