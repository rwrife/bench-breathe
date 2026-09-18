#include "core/sht40.h"

namespace bb {

Sht40Reading sht40_ticks_to_reading(uint16_t t_ticks, uint16_t rh_ticks) {
    Sht40Reading r{};
    // Datasheet §4.6 eq (2): T [°C] = -45 + 175 * St / (2^16 - 1)
    r.temp_c = -45.0f + 175.0f * static_cast<float>(t_ticks) / 65535.0f;
    // Datasheet §4.6 eq (1): RH [%RH] = -6 + 125 * Srh / (2^16 - 1), clamp [0,100]
    float rh = -6.0f + 125.0f * static_cast<float>(rh_ticks) / 65535.0f;
    if (rh > 100.0f) rh = 100.0f;
    if (rh < 0.0f) rh = 0.0f;
    r.rh_pct = rh;
    return r;
}

Sht40Error sht40_decode_measurement(const uint8_t resp[6], Sht40Reading& out) {
    uint16_t words[2];
    if (sensirion_decode_words(resp, 6, words, 2) != 2) return Sht40Error::CrcMismatch;
    out = sht40_ticks_to_reading(words[0], words[1]);
    return Sht40Error::Ok;
}

}  // namespace bb
