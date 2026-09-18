// SPS30 (U2) SHDLC codec for the UART link (SEL pin floating -> UART mode;
// J3/J2 wire RX/TX, project schematic nets PM_UART_TX/PM_UART_RX).
// Datasheet: Sensirion SPS30 v2.0 (June 2023) §5.
// Address is always 0x00. Checksum = ~(sum of ADR, CMD, [STATE], L, DATA)
// (§5.2 worked example: 0x00 0x00 0x02 0x01 0x03 -> 0xF9). Byte-stuffing per
// Table 5. Frame: 0x7E ADR CMD [STATE] LEN DATA... CHK 0x7E.
//
// This codec is a pure byte-stream state machine so it can be unit-tested
// with byte vectors transcribed from the datasheet's own example frames.
#pragma once
#include <cstdint>
#include <cstddef>

namespace bb {

namespace shdlc {
inline constexpr uint8_t kStart = 0x7E;
inline constexpr uint8_t kEsc = 0x7D;
inline constexpr uint8_t kXor = 0x20;
}  // namespace shdlc

inline uint8_t shdlc_checksum(const uint8_t* data, size_t len) {
    uint8_t sum = 0;
    for (size_t i = 0; i < len; ++i) sum += data[i];
    return static_cast<uint8_t>(~sum);
}

// Escape a payload for transmission (Table 5). out must have room; returns
// escaped length.
size_t shdlc_stuff(const uint8_t* in, size_t len, uint8_t* out, size_t cap);

// Inverse of shdlc_stuff for one byte at a time (used by the rx parser).
struct ShdlcUnstuff {
    // Feed one raw byte; sets `out_byte` and returns true when it completes
    // a data byte (or escapes). Returns false on protocol error.
    bool feed(uint8_t byte, uint8_t& out_byte);
    bool pending_escape_ = false;
};

// --- MOSI frame builders -----------------------------------------------------
// Start measurement, big-endian IEEE754 float output, subcommand 0x01
// (datasheet §5.3.1 example frame: 7E 00 00 02 01 03 F9 7E).
size_t sps30_frame_start_measurement(uint8_t out[8]);
// Stop measurement (§5.3.2): 7E 00 01 00 FF 7E.
size_t sps30_frame_stop_measurement(uint8_t out[6]);
// Read measured values (§5.3.3): 7E 00 03 00 FC 7E.
size_t sps30_frame_read_values(uint8_t out[6]);
// Device reset (§5.3.11 CMD 0xD3).
size_t sps30_frame_reset(uint8_t out[6]);

// --- Response parsing --------------------------------------------------------
// Incremental MISO frame parser. Feed raw UART bytes; when a complete frame
// with matching checksum arrives, `complete()` returns true and `data()` /
// `data_len()` expose the un-stuffed DATA field (STATE must be 0x00).
class ShdlcFrameReader {
public:
    static constexpr size_t kMaxData = 64;

    void feed(uint8_t byte);
    bool complete() const { return complete_; }
    uint8_t command() const { return command_; }
    uint8_t state() const { return state_; }
    const uint8_t* data() const { return data_; }
    size_t data_len() const { return len_; }
    bool checksum_ok() const { return checksum_ok_; }
    void reset() { *this = ShdlcFrameReader{}; }

private:
    enum class Phase : uint8_t { WaitStart, Address, Command, MaybeState, Length, Data, Checksum, WaitStop };
    Phase phase_ = Phase::WaitStart;
    uint8_t command_ = 0;
    uint8_t state_ = 0;
    uint8_t length_ = 0;
    uint8_t data_[kMaxData]{};
    size_t len_ = 0;
    uint8_t chk_ = 0;
    bool have_chk_ = false;
    bool checksum_ok_ = false;
    bool complete_ = false;
    ShdlcUnstuff rx_unstuff_{};
    // raw bytes for checksum (ADR CMD [STATE] LEN DATA, un-stuffed)
    uint8_t csum_buf_[kMaxData + 4]{};
    size_t csum_len_ = 0;
};

// Decode the 40-byte float payload from Read Measured Values (§4.3
// "IEEE754 float values" table) into named channels. pm fields in µg/m³.
struct Sps30Values {
    float pm1_0;    // mass concentration µg/m³
    float pm2_5;    // MVP PM2.5 channel
    float pm4_0;
    float pm10;
    float p0_5_nc;  // number concentrations #/cm³
    float p1_0_nc;
    float p2_5_nc;
    float p4_0_nc;
    float p10_nc;
    float typical_particle_size_um;
};
bool sps30_decode_values(const uint8_t* data, size_t len, Sps30Values& out);

}  // namespace bb
