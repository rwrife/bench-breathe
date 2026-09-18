// User-tagged event markers (fan_on, window_open, session_start, ...) —
// DAT-09: bounded length, caller must escape on export; the store itself
// keeps a fixed-capacity ring so a long label can never corrupt records.
#pragma once
#include <cstdint>
#include <cstring>

namespace bb {

inline constexpr size_t kEventTextMax = 63;  // 63 chars + NUL
// 128 entries * 84 B ≈ 10.5 KB RAM — sized for ESP32-C3 SRAM headroom
// alongside Wi-Fi buffers; event history is annotation-scale, not sample-scale.
inline constexpr uint32_t kEventRingCapacity = 128;

struct EventMarker {
    uint32_t seq;
    uint64_t mono_us;
    int64_t wall_us;
    char text[kEventTextMax + 1];
};

class EventLog {
public:
    // Returns false when text does not fit (bounded input, DAT-09).
    bool add(uint64_t mono_us, int64_t wall_us, const char* text, size_t len) {
        if (len > kEventTextMax) return false;
        EventMarker& e = ring_[head_];
        e.seq = next_seq_++;
        e.mono_us = mono_us;
        e.wall_us = wall_us;
        std::memcpy(e.text, text, len);
        e.text[len] = '\0';
        head_ = (head_ + 1) % kEventRingCapacity;
        if (count_ < kEventRingCapacity) count_++;
        return true;
    }

    uint32_t count() const { return count_; }
    uint32_t capacity() const { return kEventRingCapacity; }

    uint32_t read(uint32_t from_idx, EventMarker* out, uint32_t max) const {
        const uint32_t start = (head_ + kEventRingCapacity - count_) % kEventRingCapacity;
        uint32_t n = 0;
        while (n < max && from_idx < count_) {
            out[n++] = ring_[(start + from_idx) % kEventRingCapacity];
            from_idx++;
        }
        return n;
    }

    void clear() { head_ = count_ = 0; }  // DAT-05 erases event labels too

private:
    EventMarker ring_[kEventRingCapacity];
    uint32_t head_ = 0;
    uint32_t count_ = 0;
    uint32_t next_seq_ = 1;
};

}  // namespace bb
