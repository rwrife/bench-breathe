// Channel/sample data model shared by firmware and (via JSON rendering) the app.
// Units and validity semantics follow docs/protocol.md and requirements SNS-01/SNS-04:
// unavailable values are explicit nulls with a reason, never silently dropped.
#pragma once
#include <cstdint>

namespace bb {

// SNS-04 channel state enum. Wire values are stable; do not renumber.
enum class ChannelStatus : uint8_t {
    Ready = 0,     // "ready"
    Warming = 1,   // "warming"
    Fault = 2,     // "fault"
    Unknown = 3,   // "unknown"
};

// Reasons for a null channel value (SNS-04/SNS-01). Stable wire values.
enum class NullReason : uint8_t {
    None = 0,
    Warming = 1,          // sensor warm-up/baseline not complete
    SensorFault = 2,      // bus/protocol error or self-test failure
    PowerGated = 3,       // channel disabled by power-state gating (PWR-03)
    NotYetMeasured = 4,   // no measurement received yet
    StaleBeyondLimit = 5, // last value older than the channel's validity horizon
};

struct ChannelValue {
    bool valid = false;
    float value = 0.0f;               // meaningful only when valid
    ChannelStatus status = ChannelStatus::Unknown;
    NullReason reason = NullReason::NotYetMeasured;
    uint64_t updated_mono_us = 0;     // monotonic timestamp of last sensor update (SNS-02)
};

// Clock-quality metadata (SNS-06, protocol "clock-quality"). Stable wire values.
enum class ClockQuality : uint8_t {
    Unset = 0,       // no wall-clock source yet
    Estimated = 1,   // set once, never validated (e.g. serial-set time)
    NetworkSynced = 2,
};

// Raw record stored in history (DAT-01/DAT-03). Fixed size, trivially copyable.
struct RawRecord {
    uint32_t seq = 0;             // monotonic ordering key (SNS-06)
    uint64_t mono_us = 0;         // monotonic timestamp at record time
    int64_t wall_us = 0;          // wall-clock time; 0 when unset (see clock_q)
    ClockQuality clock_q = ClockQuality::Unset;
    ChannelValue pm25;            // µg/m³
    ChannelValue voc;             // VOC raw proxy SRAW_VOC ticks (SGP40)
    ChannelValue temp_c;          // °C
    ChannelValue rh;              // %RH
};

// 5-minute aggregate record (DAT-02 "or an equivalent documented bounded summary").
struct AggregateRecord {
    int64_t bucket_start_wall_us = 0;  // bucket boundary in wall time (0 if clock unset)
    uint32_t count = 0;                // raw records folded into this bucket
    float pm25_mean = 0.0f;            // mean over valid samples
    float voc_max = 0.0f;              // max over valid samples (proxy events matter)
    float temp_mean = 0.0f;
    float rh_mean = 0.0f;
    uint8_t valid_mask = 0;            // bit0 pm25, bit1 voc, bit2 temp, bit3 rh had >=1 valid sample
};

}  // namespace bb
