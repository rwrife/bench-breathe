// Single-line JSON health/status renderer used by the USB-serial fallback
// (COM-03). Kept allocation-free and stdio-free so it is byte-testable
// natively; the HTTP API in issue #7 reuses the same field semantics from
// docs/protocol.md. Field names here are a subset of the v0 draft; the
// final contract is finalized in #7 (COM-04).
#pragma once
#include <cstddef>
#include <cstdint>

#include "core/history.h"
#include "core/power_source.h"
#include "core/sample.h"

namespace bb {

struct HealthSnapshot {
    const char* fw_version;
    uint32_t uptime_s;
    DeviceMode mode;
    SourceState source;
    uint32_t raw_used, raw_capacity;
    uint32_t agg_used, agg_capacity;
    uint32_t oldest_seq, newest_seq;
    ClockQuality clock_q;
    ChannelStatus pm25, voc, temp, rh;
    float pm25_value, voc_raw, temp_value, rh_value;
    bool pm25_valid, voc_valid, temp_valid, rh_valid;
};

// Render one NDJSON health line into buf (NUL-terminated). Returns length
// written (excluding NUL), or 0 when buf is too small (no truncation).
size_t render_health_line(const HealthSnapshot& s, char* buf, size_t cap);

}  // namespace bb
