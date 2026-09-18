// SGP40-D-R4 (U3) command layer. Datasheet: Sensirion SGP40 v1.2 (Feb 2022).
// Bus-agnostic codec; the device HAL performs actual I2C transactions.
// I2C address 0x59 (datasheet §4.2; component-selection.md cross-check).
#pragma once
#include <cstddef>
#include <cstdint>

#include "core/crc8_sensirion.h"

namespace bb {

inline constexpr uint8_t kSgp40Address = 0x59;

// Measure raw signal (Table 8 / Table 9). Command itself is 0x26 0x0F;
// the two compensation words each carry a CRC (Table 10 conversion):
//   RH ticks    = RH/% * 65535 / 100
//   Temp ticks  = (T/°C + 45) * 65535 / 175
// Default (uncompensated) words: RH 0x8000 (+CRC 0xA2), T 0x6666 (+CRC 0x93).
inline constexpr uint16_t kSgp40RhDefault = 0x8000;
inline constexpr uint16_t kSgp40TempDefault = 0x6666;

// Build the 7-byte measure_raw_signal frame (Table 9 worked vectors:
// 0x26 0x0F 0x80 0x00 0xA2 0x66 0x66 0x93 for defaults; length 8 incl. both CRCs).
// With humidity compensation, pass measured RH/T (clamped to [0,100] %RH /
// [-45,130] °C per Table 10 range before tick conversion).
size_t sgp40_build_measure_frame(float rh_pct_or_nan, float temp_c_or_nan, uint8_t out[8]);

// Decode the 3-byte read response [SRAW msb, SRAW lsb, CRC] (Table 8,
// response length 3 incl. CRC). Returns raw ticks (SRAW_VOC) or -1 on CRC error.
int32_t sgp40_decode_raw_response(const uint8_t resp[3]);

}  // namespace bb
