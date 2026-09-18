// Portable core: no Arduino/ESP-IDF includes allowed in src/core/*.
// Sensirion 8-bit CRC used by SHT4x (Table 7 / §4.4), SGP40 (§4.6, Table 7),
// and SGP40 compensation-word checksums (Table 10).
// Properties (SHT4x datasheet v6.4 §4.4, Table 7):
//   CRC-8, polynomial 0x31, init 0xFF, no reflection, final XOR 0x00.
// Canonical datasheet vectors covered by tests:
//   SHT4x Table 7:    CRC(0xBEEF)             = 0x92
//   SGP40 Table 10:   CRC(0x8000)=0xA2  CRC(0x6666)=0x93
//                     CRC(0x0000)=0x81  CRC(0xFFFF)=0xAC
#pragma once
#include <cstddef>
#include <cstdint>

namespace bb {

uint8_t sensirion_crc8(const uint8_t* data, size_t len);

inline uint8_t sensirion_crc8_u16(uint16_t v) {
    const uint8_t bytes[2] = {static_cast<uint8_t>(v >> 8), static_cast<uint8_t>(v & 0xFF)};
    return sensirion_crc8(bytes, 2);
}

// Encode a 16-bit word as [msb, lsb, crc]. out must have room for 3 bytes.
inline void sensirion_encode_u16(uint16_t v, uint8_t out[3]) {
    out[0] = static_cast<uint8_t>(v >> 8);
    out[1] = static_cast<uint8_t>(v & 0xFF);
    out[2] = sensirion_crc8_u16(v);
}

// Decode len bytes (multiple of 3: [msb,lsb,crc]...) into up to len/3 words.
// Returns number of words decoded, or -1 on any CRC failure.
int sensirion_decode_words(const uint8_t* data, size_t len, uint16_t* out, int max_words);

}  // namespace bb
