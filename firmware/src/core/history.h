// Bounded history storage (DAT-01/DAT-02/DAT-03).
//
// Capacity calculation (static evidence for the requirement's
// "storage-capacity calculation"): compact raw records are 24 B, aggregates 32 B.
//   DAT-01: 43,200 raw records (24 h @ 2 s) -> 43,200 * 24 = 1,036,800 B (~1.04 MB)
//   DAT-02: 8,640 five-minute aggregates    ->  8,640 * 32 =   276,480 B (~0.28 MB)
//   Combined ~1.31 MB, which EXCEEDS ESP32-C3 SRAM (~400 KB), so on-device the
//   ring arrays live in a memory-mapped data partition (mmap via the device
//   HAL); native tests allocate the same layout from the heap. The History
//   object itself holds only pointers and counters (a few hundred bytes).
// Wall-clock time is stored as a 32-bit offset (seconds) from a per-store base
// stamped when wall time first becomes available; records stored before any
// clock keep wall_off = kNoWall (SNS-06: records never reorder on clock fix —
// re-export joins mono time with the corrected base instead).
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>

#include "core/sample.h"

namespace bb {

inline constexpr uint32_t kRawRingCapacity = 43200;  // DAT-01 (24 h @ 2 s)
inline constexpr uint32_t kAggRingCapacity = 8640;   // DAT-02 (30 d @ 5 min)
inline constexpr int64_t kAggBucketUs = 5LL * 60 * 1000000;
inline constexpr int32_t kNoWall = 0x7FFFFFFF;

struct CompactRecord {
    uint32_t seq;         // monotonic ordering key (SNS-06)
    uint32_t mono_s;      // mono_us >> 6; 64 µs resolution, wraps ~7.4 yr uptime
    int32_t wall_off_s;   // seconds from wall_base_us, or kNoWall
    uint8_t status;       // 2 bits per channel: pm25,voc,temp,rh (ChannelStatus)
    uint8_t _pad0;        // alignment
    uint16_t pm25;        // 0.01 µg/m³, saturating; meaningful if pm25 Ready
    uint16_t voc;         // SRAW_VOC ticks (0..65535)
    int16_t temp_c;       // 0.01 °C, saturating
    uint16_t rh;          // 0.01 %RH, saturating
    uint8_t _pad1[2];     // reserved, packed to 24 B total
};
static_assert(sizeof(CompactRecord) == 24, "record size is a capacity-calculation input");

struct AggCompact {
    int64_t bucket_start_wall_us;  // 0 when clock unset
    uint32_t count;
    float pm25_mean;
    float voc_max;
    float temp_mean;
    float rh_mean;
    uint8_t valid_mask;            // bit0 pm25, bit1 voc, bit2 temp, bit3 rh
    uint8_t _pad[3];               // folding-only: per-channel valid-sample counts
};
static_assert(sizeof(AggCompact) == 32, "aggregate size is a capacity-calculation input");

// Byte arena backing the two rings. Device: mmap'd flash partition (future
// full-capacity DAT-01 store; the baseline build uses a small RAM arena and
// documents flash spooling as an open bench-gated item).
// Native: heap block. Capacities are explicit so one code path serves both.
struct HistoryArena {
    CompactRecord* raw;
    AggCompact* agg;
    uint32_t raw_cap;
    uint32_t agg_cap;
};

inline ChannelStatus status_of_bits(uint8_t status_byte, int channel) {
    return static_cast<ChannelStatus>((status_byte >> (channel * 2)) & 0x3);
}

// DAT-03: deterministic oldest-first rollover; publishes capacity, used,
// oldest/newest timestamps. All ring state lives in the arena so the same
// object works over RAM (tests) and mmap'd flash (device).
class History {
public:
    explicit History(HistoryArena arena) : a_(arena) {}

    // Initialize counters after a fresh (erased) or restored arena. Call once
    // after boot following `restore`, or `reset_counters` for a blank store.
    void reset_counters() {
        raw_head_ = raw_count_ = agg_head_ = agg_count_ = 0;
        next_seq_ = 1;
        in_bucket_ = false;
        wall_base_set_ = false;
        wall_base_us_ = 0;
    }

    // Append a raw sample (monotonic seq assigned internally). Folds it into
    // the in-progress 5-min aggregate bucket (DAT-02) or starts a new bucket.
    void append(const RawRecord& rec);

    uint32_t raw_capacity() const { return a_.raw_cap; }
    uint32_t agg_capacity() const { return a_.agg_cap; }
    // DAT-03 used count. Note the in-progress aggregate bucket is only
    // published once it rolls over, so agg_used never counts partial data.
    uint32_t raw_used() const { return raw_count_; }
    uint32_t agg_used() const { return agg_count_; }
    bool oldest(CompactRecord& out) const;
    bool newest(CompactRecord& out) const;

    uint32_t read_raw(uint32_t from_idx, CompactRecord* out, uint32_t max) const;
    uint32_t read_agg(uint32_t from_idx, AggCompact* out, uint32_t max) const;

    bool wall_base_set() const { return wall_base_set_; }
    int64_t wall_base_us() const { return wall_base_us_; }

    // DAT-05 clear-history (configuration survives; caller persists counters).
    void clear_history() {
        raw_head_ = raw_count_ = agg_head_ = agg_count_ = 0;
        in_bucket_ = false;
    }

    struct Header {
        uint32_t magic;      // 'BBH1'
        uint32_t raw_head, raw_count, agg_head, agg_count, next_seq;
        uint8_t in_bucket;
        uint8_t flags;       // bit0 wall_base_set
        uint8_t _rfu[2];
        AggCompact bucket;   // in-progress bucket carried across reboots
        int64_t wall_base_us;
    };
    static constexpr uint32_t kHeaderMagic = 0x31484242;  // "BBH1"

    // Small control block for persistence (rings persist in place on mmap'd
    // flash; native tests persist the whole arena via the same calls).
    void save_header(uint8_t* buf, size_t cap) const;  // writes sizeof(Header)
    bool load_header(const uint8_t* buf, size_t len);  // false on magic/size mismatch

private:
    void publish_bucket();

    HistoryArena a_;
    uint32_t raw_head_ = 0;
    uint32_t raw_count_ = 0;
    uint32_t agg_head_ = 0;
    uint32_t agg_count_ = 0;
    uint32_t next_seq_ = 1;
    bool in_bucket_ = false;
    AggCompact bucket_{};
    bool wall_base_set_ = false;
    int64_t wall_base_us_ = 0;
};

}  // namespace bb
