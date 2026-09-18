#include "core/sensors.h"

#include <cmath>

namespace bb {

bool Sht40Driver::measure(Sht40Reading& out) {
    const uint8_t cmd = sht40_cmd::MeasureHighRepNoStretch;
    if (!i2c_.write(kSht40Address, &cmd, 1)) return false;
    clk_.delay_ms(12);  // > tMEAS,h max 8.3 ms (§3.1)
    uint8_t resp[6];
    if (!i2c_.read(kSht40Address, resp, 6)) return false;
    return sht40_decode_measurement(resp, out) == Sht40Error::Ok;
}

bool Sgp40Driver::measure_raw(float rh_pct, float temp_c, uint16_t& sraw_voc) {
    uint8_t frame[8];
    const size_t len = sgp40_build_measure_frame(rh_pct, temp_c, frame);
    if (!i2c_.write(kSgp40Address, frame, len)) return false;
    clk_.delay_ms(32);  // > Table 8 max measurement duration 30 ms
    uint8_t resp[3];
    if (!i2c_.read(kSgp40Address, resp, 3)) return false;
    const int32_t raw = sgp40_decode_raw_response(resp);
    if (raw < 0) return false;
    sraw_voc = static_cast<uint16_t>(raw);
    return true;
}

void Sps30Driver::pump_rx() {
    while (uart_.available() > 0) {
        reader_.feed(uart_.read_byte());
        if (reader_.complete()) {
            if (reader_.command() == 0x03 && reader_.state() == 0x00 && reader_.checksum_ok() &&
                sps30_decode_values(reader_.data(), reader_.data_len(), values_)) {
                have_values_ = true;
            }
            reader_.reset();
            return;  // one frame per pump call is sufficient for polling
        }
    }
}

bool Sps30Driver::start_measurement() {
    uint8_t frame[8];
    const size_t len = sps30_frame_start_measurement(frame);
    uart_.write(frame, len);
    // Wait out the empty ack frame window (§5.3.1 max response 20 ms).
    clk_.delay_ms(25);
    pump_rx();
    started_ = true;
    return true;  // transport-level start; value readiness is tracked by the Sampler
}

bool Sps30Driver::poll_values(Sps30Values& out) {
    if (!started_) return false;
    have_values_ = false;
    uint8_t frame[6];
    const size_t len = sps30_frame_read_values(frame);
    uart_.write(frame, len);
    // §5.3.3 max response 20 ms; give the pump 3 x 5 ms slices.
    for (int i = 0; i < 3 && !have_values_; ++i) {
        clk_.delay_ms(5);
        pump_rx();
    }
    if (!have_values_) return false;
    out = values_;
    return true;
}

void Sampler::request_pm_start(uint64_t now_mono_ms) {
    pm_start_requested_ = true;
    pm.started_mono_ms = now_mono_ms;
    pm.has_start = false;  // becomes true once start command acknowledged path completes
}

void Sampler::tick(uint64_t now_mono_ms, bool power_allows_pm, RawRecord& out) {
    // Temperature/humidity first: feeds SGP40 humidity compensation (§3.1).
    bool ok = sht_.measure(out_th_);
    out.temp_c.valid = ok;
    out.temp_c.value = ok ? out_th_.temp_c : 0.0f;
    out.temp_c.status = ok ? ChannelStatus::Ready : ChannelStatus::Fault;
    out.temp_c.reason = ok ? NullReason::None : NullReason::SensorFault;
    out.temp_c.updated_mono_us = now_mono_ms * 1000ULL;

    out.rh.valid = ok;
    out.rh.value = ok ? out_th_.rh_pct : 0.0f;
    out.rh.status = ok ? ChannelStatus::Ready : ChannelStatus::Fault;
    out.rh.reason = ok ? NullReason::None : NullReason::SensorFault;
    out.rh.updated_mono_us = now_mono_ms * 1000ULL;

    // VOC raw proxy with compensation from fresh T/RH when available.
    uint16_t sraw = 0;
    if (sgp_.measure_raw(ok ? out_th_.rh_pct : NAN, ok ? out_th_.temp_c : NAN, sraw)) {
        voc.has_value = true;
        voc.last_raw = sraw;
        voc.last_ok_mono_ms = now_mono_ms;
        if (!voc.has_start) {
            voc.started_mono_ms = now_mono_ms;
            voc.has_start = true;
        }
    } else {
        voc.status = ChannelStatus::Fault;
    }
    if (voc.has_value) {
        const bool conditioning = (now_mono_ms - voc.started_mono_ms) < kSgp40WarmingMs;
        voc.status = conditioning ? ChannelStatus::Warming : ChannelStatus::Ready;
        out.voc.valid = true;
        out.voc.value = static_cast<float>(voc.last_raw);
        out.voc.status = voc.status;
        out.voc.reason = NullReason::None;
        out.voc.updated_mono_us = voc.last_ok_mono_ms * 1000ULL;
    } else {
        out.voc.valid = false;
        out.voc.status = voc.status;
        out.voc.reason = voc.status == ChannelStatus::Fault ? NullReason::SensorFault
                                                           : NullReason::NotYetMeasured;
        out.voc.value = 0.0f;
        out.voc.updated_mono_us = 0;
    }

    // PM channel: power-gated when the source state forbids the fan (PWR-03).
    if (!power_allows_pm) {
        pm.status = ChannelStatus::Unknown;
        out.pm25.valid = false;
        out.pm25.status = ChannelStatus::Unknown;
        out.pm25.reason = NullReason::PowerGated;
        out.pm25.value = 0.0f;
        out.pm25.updated_mono_us = 0;
        return;
    }
    if (pm_start_requested_ && !pm_started_) {
        sps_.start_measurement();
        pm_started_ = true;
        pm_start_requested_ = false;
        pm.started_mono_ms = now_mono_ms;
        pm.has_start = true;
    }
    Sps30Values v;
    if (sps_.poll_values(v)) {
        pm.has_value = true;
        pm.last_value = v.pm2_5;
        pm.last_ok_mono_ms = now_mono_ms;
    }
    if (pm.has_value) {
        const bool warming = !pm.has_start || (now_mono_ms - pm.started_mono_ms) < kSps30WarmingMs;
        pm.status = warming ? ChannelStatus::Warming : ChannelStatus::Ready;
        out.pm25.valid = true;
        out.pm25.value = pm.last_value;
        out.pm25.status = pm.status;
        out.pm25.reason = NullReason::None;
        out.pm25.updated_mono_us = pm.last_ok_mono_ms * 1000ULL;
    } else {
        // No fresh value yet (empty frame / just started): explicit null with
        // reason; if we had a prior value it would repeat with retained age.
        out.pm25.valid = false;
        out.pm25.status = pm.has_start ? ChannelStatus::Warming : ChannelStatus::Unknown;
        out.pm25.reason = NullReason::NotYetMeasured;
        out.pm25.value = 0.0f;
        out.pm25.updated_mono_us = 0;
    }
}

}  // namespace bb
