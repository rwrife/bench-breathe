// Versioned configuration with explicit validation (SNS-03, PWR-07):
// invalid values are rejected, never silently clamped. Writes go through
// a staged apply so a torn write cannot leave partially committed config.
#pragma once
#include <cstddef>
#include <cstdint>

namespace bb {

inline constexpr uint32_t kIntervalMinMs = 2000;   // SNS-03 lower bound
inline constexpr uint32_t kIntervalMaxMs = 60000;  // SNS-03 upper bound
inline constexpr uint32_t kDefaultIntervalMs = 2000;
inline constexpr size_t kLabelMaxLen = 31;         // 31 chars + NUL

struct Config {
    uint32_t schema = 1;                    // configuration schema version
    uint32_t interval_ms = kDefaultIntervalMs;
    char label[kLabelMaxLen + 1] = "bench-breathe";
};

enum class ConfigError : uint8_t {
    Ok = 0,
    IntervalOutOfRange,   // outside 2–60 s; reject rather than clamp (SNS-03)
    LabelTooLong,
};

// Validate a candidate config before committing (DAT-04: reject before stage).
ConfigError validate_config(const Config& candidate);

// Copy with truncation-free semantics: returns false (and leaves dst
// untouched) when src does not fit the bounded label field (DAT-09 style bound).
bool set_label(Config& cfg, const char* src, size_t src_len);

}  // namespace bb
