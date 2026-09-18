#include "core/sgp40.h"

#include <cmath>

namespace bb {

namespace {
uint16_t rh_to_ticks(float rh_pct) {
    if (std::isnan(rh_pct)) return kSgp40RhDefault;
    if (rh_pct < 0.0f) rh_pct = 0.0f;
    if (rh_pct > 100.0f) rh_pct = 100.0f;
    // Table 10: RH/ticks = RH/% × 65535 / 100
    return static_cast<uint16_t>(rh_pct * 65535.0f / 100.0f + 0.5f);
}
uint16_t temp_to_ticks(float temp_c) {
    if (std::isnan(temp_c)) return kSgp40TempDefault;
    if (temp_c < -45.0f) temp_c = -45.0f;
    if (temp_c > 130.0f) temp_c = 130.0f;
    // Table 10: T/ticks = (T/°C + 45) × 65535 / 175
    return static_cast<uint16_t>((temp_c + 45.0f) * 65535.0f / 175.0f + 0.5f);
}
}  // namespace

size_t sgp40_build_measure_frame(float rh_pct_or_nan, float temp_c_or_nan, uint8_t out[8]) {
    out[0] = 0x26;
    out[1] = 0x0F;
    sensirion_encode_u16(rh_to_ticks(rh_pct_or_nan), out + 2);
    sensirion_encode_u16(temp_to_ticks(temp_c_or_nan), out + 5);
    return 8;
}

int32_t sgp40_decode_raw_response(const uint8_t resp[3]) {
    uint16_t word;
    if (sensirion_decode_words(resp, 3, &word, 1) != 1) return -1;
    return word;
}

}  // namespace bb
