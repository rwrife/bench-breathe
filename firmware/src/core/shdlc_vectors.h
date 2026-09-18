// Frame vectors for SPS30 tests. The all-zero payload response is the exact
// datasheet v2.0 §5.3.3 example (7E 00 03 00 28 <40 x 0x00> D4 7E, CHK 0xD4
// is only valid for the zero payload). For non-zero payloads the frame is
// rebuilt with the §5.2 checksum rule and Table 5 stuffing.
#pragma once
#include <cstdint>
#include <cstring>
#include <vector>

#include "core/sps30.h"

namespace bb {

inline std::vector<uint8_t> sps30_test_values_frame_zeroed() {
    std::vector<uint8_t> f = {0x7E, 0x00, 0x03, 0x00, 0x28};
    f.insert(f.end(), 40, 0x00);
    f.push_back(0xD4);
    f.push_back(0x7E);
    return f;
}

// Build a valid Read Measured Values response with the given PM2.5 float in
// the §4.3 big-endian IEEE754 slot (payload offset 4), checksum computed per
// §5.2 and stuffing per Table 5.
inline std::vector<uint8_t> sps30_test_values_frame_pm25(float pm25) {
    uint8_t raw[4 + 40 + 1];
    raw[0] = 0x00; raw[1] = 0x03; raw[2] = 0x00; raw[3] = 0x28;
    std::memset(raw + 4, 0, 40);
    uint32_t bits;
    std::memcpy(&bits, &pm25, 4);
    raw[4 + 4] = static_cast<uint8_t>(bits >> 24);
    raw[4 + 5] = static_cast<uint8_t>(bits >> 16);
    raw[4 + 6] = static_cast<uint8_t>(bits >> 8);
    raw[4 + 7] = static_cast<uint8_t>(bits);
    raw[4 + 40] = shdlc_checksum(raw, 4 + 40);
    std::vector<uint8_t> f = {shdlc::kStart};
    f.resize(1 + 64);
    const size_t n = shdlc_stuff(raw, sizeof(raw), f.data() + 1, 64);
    f.resize(1 + n);
    f.push_back(shdlc::kStart);
    return f;
}

}  // namespace bb
