#include "core/config.h"

#include <cstring>

namespace bb {

ConfigError validate_config(const Config& candidate) {
    if (candidate.interval_ms < kIntervalMinMs || candidate.interval_ms > kIntervalMaxMs) {
        return ConfigError::IntervalOutOfRange;
    }
    if (std::strlen(candidate.label) > kLabelMaxLen) return ConfigError::LabelTooLong;
    return ConfigError::Ok;
}

bool set_label(Config& cfg, const char* src, size_t src_len) {
    if (src_len > kLabelMaxLen) return false;
    std::memcpy(cfg.label, src, src_len);
    cfg.label[src_len] = '\0';
    return true;
}

}  // namespace bb
