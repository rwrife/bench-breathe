#include "core/history.h"

namespace bb {

namespace {
constexpr int32_t clamp_i16(float v) {
    if (v > 32767.0f) return 32767;
    if (v < -32768.0f) return -32768;
    return static_cast<int32_t>(v);
}
constexpr uint16_t clamp_u16(float v) {
    if (v > 65535.0f) return 65535;
    if (v < 0.0f) return 0;
    return static_cast<uint16_t>(v);
}
// Incremental mean update over valid samples only:
// mean_n = mean_{n-1} + (value - mean_{n-1}) / n.
inline void mean_update(float& mean, uint8_t& n, float value) {
    if (n == 255) return;  // defensive saturate (bucket max ~150 @ 2 s / 5 min)
    n++;
    mean += (value - mean) / static_cast<float>(n);
}
}  // namespace

void History::append(const RawRecord& rec) {
    if (!wall_base_set_ && rec.clock_q != ClockQuality::Unset && rec.wall_us > 0) {
        wall_base_us_ = rec.wall_us;  // stamp base once; existing records keep kNoWall
        wall_base_set_ = true;
    }

    CompactRecord cr{};
    cr.seq = next_seq_++;
    cr.mono_s = static_cast<uint32_t>(rec.mono_us >> 6);
    if (wall_base_set_ && rec.clock_q != ClockQuality::Unset && rec.wall_us >= wall_base_us_) {
        const int64_t off = (rec.wall_us - wall_base_us_) / 1000000;
        cr.wall_off_s = off > kNoWall - 1 ? kNoWall - 1 : static_cast<int32_t>(off);
    } else {
        cr.wall_off_s = kNoWall;
    }

    // Status bits, channel order: pm25(0), voc(1), temp(2), rh(3).
    cr.status = static_cast<uint8_t>(
        (static_cast<uint8_t>(rec.pm25.status) & 0x3) |
        ((static_cast<uint8_t>(rec.voc.status) & 0x3) << 2) |
        ((static_cast<uint8_t>(rec.temp_c.status) & 0x3) << 4) |
        ((static_cast<uint8_t>(rec.rh.status) & 0x3) << 6));
    cr.pm25 = rec.pm25.valid ? clamp_u16(rec.pm25.value * 100.0f) : 0;
    cr.voc = rec.voc.valid ? clamp_u16(rec.voc.value) : 0;
    cr.temp_c = static_cast<int16_t>(rec.temp_c.valid ? clamp_i16(rec.temp_c.value * 100.0f) : 0);
    cr.rh = rec.rh.valid ? clamp_u16(rec.rh.value * 100.0f) : 0;

    a_.raw[raw_head_] = cr;
    raw_head_ = (raw_head_ + 1) % a_.raw_cap;
    if (raw_count_ < a_.raw_cap) raw_count_++;  // DAT-03 oldest-first rollover

    // DAT-02 aggregate folding. Mean fields carry running means over VALID
    // samples (per-channel counts in _pad[0..2]); voc_max carries the maximum.
    const int64_t bucket =
        (rec.clock_q != ClockQuality::Unset && rec.wall_us > 0)
            ? (rec.wall_us / kAggBucketUs) * kAggBucketUs
            : 0;  // no-clock records fold into one rolling bucket keyed 0
    if (!in_bucket_ || bucket != bucket_.bucket_start_wall_us) {
        publish_bucket();
        bucket_ = AggCompact{};
        bucket_.bucket_start_wall_us = bucket;
        in_bucket_ = true;
    }
    bucket_.count++;
    if (rec.pm25.valid) { bucket_.valid_mask |= 1; mean_update(bucket_.pm25_mean, bucket_._pad[0], rec.pm25.value); }
    if (rec.voc.valid) {
        if (!(bucket_.valid_mask & 2) || rec.voc.value > bucket_.voc_max) bucket_.voc_max = rec.voc.value;
        bucket_.valid_mask |= 2;
    }
    if (rec.temp_c.valid) { bucket_.valid_mask |= 4; mean_update(bucket_.temp_mean, bucket_._pad[1], rec.temp_c.value); }
    if (rec.rh.valid) { bucket_.valid_mask |= 8; mean_update(bucket_.rh_mean, bucket_._pad[2], rec.rh.value); }
}

void History::publish_bucket() {
    if (in_bucket_ && bucket_.count > 0) {
        a_.agg[agg_head_] = bucket_;
        agg_head_ = (agg_head_ + 1) % a_.agg_cap;
        if (agg_count_ < a_.agg_cap) agg_count_++;
    }
    in_bucket_ = false;
}

bool History::oldest(CompactRecord& out) const {
    if (raw_count_ == 0) return false;
    const uint32_t idx = (raw_head_ + a_.raw_cap - raw_count_) % a_.raw_cap;
    out = a_.raw[idx];
    return true;
}

bool History::newest(CompactRecord& out) const {
    if (raw_count_ == 0) return false;
    out = a_.raw[(raw_head_ + a_.raw_cap - 1) % a_.raw_cap];
    return true;
}

uint32_t History::read_raw(uint32_t from_idx, CompactRecord* out, uint32_t max) const {
    const uint32_t start = (raw_head_ + a_.raw_cap - raw_count_) % a_.raw_cap;
    uint32_t n = 0;
    while (n < max && from_idx < raw_count_) {
        out[n++] = a_.raw[(start + from_idx) % a_.raw_cap];
        from_idx++;
    }
    return n;
}

uint32_t History::read_agg(uint32_t from_idx, AggCompact* out, uint32_t max) const {
    const uint32_t start = (agg_head_ + a_.agg_cap - agg_count_) % a_.agg_cap;
    uint32_t n = 0;
    while (n < max && from_idx < agg_count_) {
        out[n++] = a_.agg[(start + from_idx) % a_.agg_cap];
        from_idx++;
    }
    return n;
}

void History::save_header(uint8_t* buf, size_t cap) const {
    if (cap < sizeof(Header)) return;
    Header h{};
    h.magic = kHeaderMagic;
    h.raw_head = raw_head_;
    h.raw_count = raw_count_;
    h.agg_head = agg_head_;
    h.agg_count = agg_count_;
    h.next_seq = next_seq_;
    h.in_bucket = in_bucket_ ? 1 : 0;
    h.flags = wall_base_set_ ? 1 : 0;
    h.bucket = bucket_;
    h.wall_base_us = wall_base_us_;
    std::memcpy(buf, &h, sizeof(Header));
}

bool History::load_header(const uint8_t* buf, size_t len) {
    if (len < sizeof(Header)) return false;
    Header h{};
    std::memcpy(&h, buf, sizeof(Header));
    if (h.magic != kHeaderMagic) return false;
    if (h.raw_count > a_.raw_cap || h.agg_count > a_.agg_cap) return false;
    if (h.raw_head >= a_.raw_cap || h.agg_head >= a_.agg_cap) return false;
    raw_head_ = h.raw_head;
    raw_count_ = h.raw_count;
    agg_head_ = h.agg_head;
    agg_count_ = h.agg_count;
    next_seq_ = h.next_seq;
    in_bucket_ = h.in_bucket != 0;
    bucket_ = h.bucket;
    wall_base_set_ = (h.flags & 1) != 0;
    wall_base_us_ = h.wall_base_us;
    return true;
}

}  // namespace bb
