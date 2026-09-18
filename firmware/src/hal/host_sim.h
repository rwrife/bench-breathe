// Host-side fake buses for native unit tests. These emulate just enough
// sensor behavior (address dispatch, command timing, response framing) to
// drive the portable drivers and the Sampler end-to-end on a dev machine.
// Evidence boundary: fakes prove *bus sequencing and codec plumbing*; the
// codec math itself is proven against datasheet vectors in test_codec.cpp.
// Nothing here proves behavior on real silicon (BENCH class, pending).
#pragma once
#include <deque>
#include <vector>

#include "core/hal.h"
#include "core/crc8_sensirion.h"

namespace bb::sim {

struct FakeClock : Clock {
    uint64_t now_us = 0;
    uint64_t monotonic_us() override { return now_us; }
    void delay_ms(uint32_t ms) override { now_us += static_cast<uint64_t>(ms) * 1000ULL; }
    void advance_ms(uint64_t ms) { now_us += ms * 1000ULL; }
};

struct FakeI2c : I2c {
    struct Device {
        uint8_t addr;
        // Returns response bytes for the read phase following this write.
        std::vector<uint8_t> response;
        bool nack = false;
    };
    std::vector<Device> devices;
    // Scripted per-address: last write's response is queued for the next read.
    struct PendingRead {
        uint8_t addr;
        std::deque<uint8_t> bytes;
    };
    std::deque<PendingRead> pending;
    std::vector<uint8_t> last_write;

    bool write(uint8_t addr, const uint8_t* data, size_t len) override {
        last_write.assign(data, data + len);
        for (auto& d : devices) {
            if (d.addr == addr) {
                if (d.nack) return false;
                if (!d.response.empty()) pending.push_back({addr, std::deque<uint8_t>(d.response.begin(), d.response.end())});
                return true;
            }
        }
        return false;  // no device at address
    }
    bool read(uint8_t addr, uint8_t* out, size_t len) override {
        if (pending.empty() || pending.front().addr != addr) return false;
        auto& q = pending.front().bytes;
        if (q.size() < len) return false;
        for (size_t i = 0; i < len; ++i) out[i] = q.front(), q.pop_front();
        pending.pop_front();
        return true;
    }
    void set_response(uint8_t addr, std::vector<uint8_t> resp) {
        for (auto& d : devices) if (d.addr == addr) { d.response = std::move(resp); return; }
        devices.push_back({addr, std::move(resp), false});
    }
    void set_nack(uint8_t addr, bool nack) {
        for (auto& d : devices) if (d.addr == addr) { d.nack = nack; return; }
        devices.push_back({addr, {}, nack});
    }
};

struct FakeUart : Uart {
    std::deque<uint8_t> tx_seen;          // what the driver transmitted
    std::deque<uint8_t> rx_pending;       // what the fake sensor will send
    void write(const uint8_t* data, size_t len) override {
        tx_seen.insert(tx_seen.end(), data, data + len);
    }
    int available() override { return static_cast<int>(rx_pending.size()); }
    uint8_t read_byte() override { auto b = rx_pending.front(); rx_pending.pop_front(); return b; }
    void queue_rx(std::vector<uint8_t> bytes) {
        rx_pending.insert(rx_pending.end(), bytes.begin(), bytes.end());
    }
    std::vector<uint8_t> take_tx() {
        std::vector<uint8_t> out(tx_seen.begin(), tx_seen.end());
        tx_seen.clear();
        return out;
    }
};

// Small helpers to assemble valid CRC'd sensor responses in tests.
inline std::vector<uint8_t> sht40_response(uint16_t t_ticks, uint16_t rh_ticks) {
    std::vector<uint8_t> r(6);
    sensirion_encode_u16(t_ticks, r.data());
    sensirion_encode_u16(rh_ticks, r.data() + 3);
    return r;
}
inline std::vector<uint8_t> sgp40_response(uint16_t sraw) {
    std::vector<uint8_t> r(3);
    sensirion_encode_u16(sraw, r.data());
    return r;
}

}  // namespace bb::sim
