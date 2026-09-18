#include "core/crc8_sensirion.h"

namespace bb {

uint8_t sensirion_crc8(const uint8_t* data, size_t len) {
    uint8_t crc = 0xFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            if (crc & 0x80) {
                crc = static_cast<uint8_t>((crc << 1) ^ 0x31);  // poly x^8+x^5+x^4+1
            } else {
                crc = static_cast<uint8_t>(crc << 1);
            }
        }
    }
    return crc;  // final XOR 0x00
}

int sensirion_decode_words(const uint8_t* data, size_t len, uint16_t* out, int max_words) {
    if (len % 3 != 0) return -1;
    int words = static_cast<int>(len / 3);
    if (words > max_words) return -1;
    for (int w = 0; w < words; ++w) {
        const uint8_t* p = data + w * 3;
        if (sensirion_crc8(p, 2) != p[2]) return -1;
        out[w] = static_cast<uint16_t>((p[0] << 8) | p[1]);
    }
    return words;
}

}  // namespace bb
