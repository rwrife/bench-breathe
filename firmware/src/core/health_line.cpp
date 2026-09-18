#include "core/health_line.h"

#include <cstdio>
#include <cstring>

namespace bb {

namespace {
const char* mode_str(DeviceMode m) {
    switch (m) {
        case DeviceMode::RecoveryOnly: return "recovery";
        case DeviceMode::FullSensing: return "full";
        case DeviceMode::Suspended: return "suspended";
        case DeviceMode::Error: return "error";
    }
    return "error";
}
const char* source_str(SourceState s) {
    switch (s) {
        case SourceState::NoVbus: return "no_vbus";
        case SourceState::DefaultUsbCc: return "default_cc";
        case SourceState::Cc15A: return "cc_1a5";
        case SourceState::Cc3A: return "cc_3a";
        case SourceState::UnknownCc: return "unknown_cc";
    }
    return "unknown_cc";
}
const char* status_str(ChannelStatus st) {
    switch (st) {
        case ChannelStatus::Ready: return "ready";
        case ChannelStatus::Warming: return "warming";
        case ChannelStatus::Fault: return "fault";
        case ChannelStatus::Unknown: return "unknown";
    }
    return "unknown";
}
const char* clock_str(ClockQuality q) {
    switch (q) {
        case ClockQuality::Unset: return "unset";
        case ClockQuality::Estimated: return "estimated";
        case ClockQuality::NetworkSynced: return "network";
    }
    return "unset";
}
}  // namespace

size_t render_health_line(const HealthSnapshot& s, char* buf, size_t cap) {
    // Valid channels render numbers; invalid render null (SNS-04: explicit
    // nulls, never silent drops or zeros-as-data).
    char pm[32], voc[32], t[32], rh[32];
    auto num = [](float v, char out[32]) {
        std::snprintf(out, 32, "%.2f", static_cast<double>(v));
    };
    if (s.pm25_valid) num(s.pm25_value, pm); else std::strcpy(pm, "null");
    if (s.voc_valid) num(s.voc_raw, voc); else std::strcpy(voc, "null");
    if (s.temp_valid) num(s.temp_value, t); else std::strcpy(t, "null");
    if (s.rh_valid) num(s.rh_value, rh); else std::strcpy(rh, "null");

    const int n = std::snprintf(
        buf, cap,
        "{\"protocol\":\"v0\",\"fw\":\"%s\",\"uptime_s\":%u,\"mode\":\"%s\",\"source\":\"%s\","
        "\"storage\":{\"raw_used\":%u,\"raw_capacity\":%u,\"agg_used\":%u,\"agg_capacity\":%u,"
        "\"oldest_seq\":%u,\"newest_seq\":%u},\"clock\":\"%s\","
        "\"channels\":{"
        "\"pm25\":{\"status\":\"%s\",\"value\":%s,\"unit\":\"ug_m3\"},"
        "\"voc_raw\":{\"status\":\"%s\",\"value\":%s,\"unit\":\"ticks\"},"
        "\"temperature_c\":{\"status\":\"%s\",\"value\":%s,\"unit\":\"c\"},"
        "\"humidity_pct\":{\"status\":\"%s\",\"value\":%s,\"unit\":\"pct\"}}}\n",
        s.fw_version, s.uptime_s, mode_str(s.mode), source_str(s.source), s.raw_used,
        s.raw_capacity, s.agg_used, s.agg_capacity, s.oldest_seq, s.newest_seq,
        clock_str(s.clock_q), status_str(s.pm25), pm, status_str(s.voc), voc,
        status_str(s.temp), t, status_str(s.rh), rh);
    if (n < 0 || static_cast<size_t>(n) >= cap) return 0;  // would truncate -> refuse
    return static_cast<size_t>(n);
}

}  // namespace bb
