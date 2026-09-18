#include "core/sps30.h"

#include <cstring>

namespace bb {

size_t shdlc_stuff(const uint8_t* in, size_t len, uint8_t* out, size_t cap) {
    size_t o = 0;
    for (size_t i = 0; i < len; ++i) {
        const uint8_t b = in[i];
        uint8_t repl[2];
        size_t add = 1;
        repl[0] = b;
        switch (b) {
            case 0x7E: repl[0] = shdlc::kEsc; repl[1] = 0x7E ^ shdlc::kXor; add = 2; break;
            case 0x7D: repl[0] = shdlc::kEsc; repl[1] = 0x7D ^ shdlc::kXor; add = 2; break;
            case 0x11: repl[0] = shdlc::kEsc; repl[1] = 0x11 ^ shdlc::kXor; add = 2; break;
            case 0x13: repl[0] = shdlc::kEsc; repl[1] = 0x13 ^ shdlc::kXor; add = 2; break;
            default: break;
        }
        if (o + add > cap) return o;
        out[o++] = repl[0];
        if (add == 2) out[o++] = repl[1];
    }
    return o;
}

bool ShdlcUnstuff::feed(uint8_t byte, uint8_t& out_byte) {
    if (pending_escape_) {
        pending_escape_ = false;
        if (byte != 0x5E && byte != 0x5D && byte != 0x31 && byte != 0x33) return false;
        out_byte = static_cast<uint8_t>(byte ^ shdlc::kXor);
        return true;
    }
    if (byte == shdlc::kEsc) {
        pending_escape_ = true;
        return false;
    }
    if (byte == shdlc::kStart) return false;  // unexpected start mid-frame
    out_byte = byte;
    return true;
}

namespace {
// Build a MOSI frame: 7E 00 CMD LEN DATA... CHK 7E (ADDR always 0).
size_t build_mosi(uint8_t cmd, const uint8_t* data, size_t dlen, uint8_t* out, size_t cap) {
    uint8_t raw[64];
    if (dlen > sizeof(raw) - 4) return 0;
    raw[0] = 0x00;       // ADR
    raw[1] = cmd;        // CMD
    raw[2] = static_cast<uint8_t>(dlen);  // L
    for (size_t i = 0; i < dlen; ++i) raw[3 + i] = data[i];
    const size_t pre = 3 + dlen;
    raw[pre] = shdlc_checksum(raw, pre);
    size_t o = 0;
    if (cap < pre + 1 + 2) return 0;
    out[o++] = shdlc::kStart;
    o += shdlc_stuff(raw, pre + 1, out + o, cap - o - 1);
    out[o++] = shdlc::kStart;
    return o;
}
}  // namespace

size_t sps30_frame_start_measurement(uint8_t out[8]) {
    // §5.3.1: subcommand 0x01, format 0x03 (big-endian IEEE754 floats).
    const uint8_t data[2] = {0x01, 0x03};
    return build_mosi(0x00, data, 2, out, 8);
}
size_t sps30_frame_stop_measurement(uint8_t out[6]) { return build_mosi(0x01, nullptr, 0, out, 6); }
size_t sps30_frame_read_values(uint8_t out[6]) { return build_mosi(0x03, nullptr, 0, out, 6); }
size_t sps30_frame_reset(uint8_t out[6]) { return build_mosi(0xD3, nullptr, 0, out, 6); }

void ShdlcFrameReader::feed(uint8_t byte) {
    if (complete_) return;
    // Byte 0 of every frame (ADR) and all subsequent payload bytes pass
    // through the un-stuffer; frame delimiters stay literal 0x7E.
    uint8_t b = byte;
    if (phase_ != Phase::WaitStart && byte == shdlc::kStart) {
        // Frame boundary.
        if (phase_ == Phase::WaitStop) {
            complete_ = true;
        } else {
            reset();  // truncated/garbage frame; resync on this start byte
        }
        return;
    }
    if (phase_ != Phase::WaitStart) {
        if (!rx_unstuff_.feed(byte, b)) {
            if (rx_unstuff_.pending_escape_) return;  // wait for escape byte
            reset();  // bad escape -> resync
            return;
        }
    }

    switch (phase_) {
        case Phase::WaitStart:
            if (byte == shdlc::kStart) phase_ = Phase::Address;
            return;
        case Phase::Address:
            csum_buf_[csum_len_++] = b;
            phase_ = Phase::Command;
            return;
        case Phase::Command:
            command_ = b;
            csum_buf_[csum_len_++] = b;
            phase_ = Phase::MaybeState;  // MISO header byte after CMD is STATE
            return;
        case Phase::MaybeState:
            state_ = b;
            csum_buf_[csum_len_++] = b;
            phase_ = Phase::Length;
            return;
        case Phase::Length:
            length_ = b;
            csum_buf_[csum_len_++] = b;
            if (length_ > kMaxData) { reset(); return; }
            phase_ = length_ == 0 ? Phase::Checksum : Phase::Data;
            return;
        case Phase::Data:
            if (len_ < kMaxData) {
                data_[len_++] = b;
                if (csum_len_ < sizeof(csum_buf_)) csum_buf_[csum_len_++] = b;
            }
            if (len_ == length_) phase_ = Phase::Checksum;
            return;
        case Phase::Checksum:
            chk_ = b;
            checksum_ok_ = shdlc_checksum(csum_buf_, csum_len_) == chk_;
            phase_ = Phase::WaitStop;
            return;
        case Phase::WaitStop:
            reset();  // shouldn't happen; start byte handles completion
            return;
    }
}

bool sps30_decode_values(const uint8_t* data, size_t len, Sps30Values& out) {
    if (len < 40) return false;
    auto f = [&](size_t off) {
        uint32_t bits = (static_cast<uint32_t>(data[off]) << 24) |
                        (static_cast<uint32_t>(data[off + 1]) << 16) |
                        (static_cast<uint32_t>(data[off + 2]) << 8) |
                        static_cast<uint32_t>(data[off + 3]);
        float v;
        std::memcpy(&v, &bits, 4);
        return v;
    };
    out.pm1_0 = f(0);
    out.pm2_5 = f(4);
    out.pm4_0 = f(8);
    out.pm10 = f(12);
    out.p0_5_nc = f(16);
    out.p1_0_nc = f(20);
    out.p2_5_nc = f(24);
    out.p4_0_nc = f(28);
    out.p10_nc = f(32);
    out.typical_particle_size_um = f(36);
    return true;
}

}  // namespace bb
