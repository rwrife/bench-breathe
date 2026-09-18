// Bench Breathe firmware baseline — device glue only. All logic lives in
// src/core (unit-tested natively); this file wires the ESP32-C3 Arduino HAL
// to the Sampler/History/Button/power gating and streams NDJSON health lines
// over USB CDC (the serial fallback path, COM-03).
//
// OUT OF SCOPE for this baseline (tracked by issue #7 protocol finalization):
// full HTTP API, pairing/authorization (COM-07), Wi-Fi provisioning/setup
// mode UI (COM-06 flow beyond the button event), full-capacity flash history
// (mmap partition), and OTA/update flow. See firmware/README.md.
#include <Arduino.h>

#include "core/button.h"
#include "core/config.h"
#include "core/events.h"
#include "core/health_line.h"
#include "core/history.h"
#include "core/power_source.h"
#include "core/sensors.h"
#include "device_hal.h"

namespace {

constexpr char kFwVersion[] = "0.1.0-baseline";

// RAM arena for the baseline build. Full DAT-01 capacity (~1.04 MB raw +
// 0.28 MB agg) requires the mmap'd flash partition and is deliberately NOT
// claimed here; this arena bounds a shorter session history until then
// (4096 raw records = ~2.3 h at the 2 s default interval; 288 published
// 5-min aggregates = 24 h, satisfying DAT-02's window but not the 30-day
// requirement — both tracked as open items for the flash-store work).
constexpr uint32_t kBaselineRawCap = 4096;
constexpr uint32_t kBaselineAggCap = 288;
bb::CompactRecord g_raw[kBaselineRawCap];
bb::AggCompact g_agg[kBaselineAggCap];

bb::device::ArduClock clock_;
bb::device::ArduI2c i2c_;
bb::device::ArduUart uart_;
bb::Sht40Driver sht_(i2c_, clock_);
bb::Sgp40Driver sgp_(i2c_, clock_);
bb::Sps30Driver sps_(uart_, clock_);
bb::Sampler sampler_(sht_, sgp_, sps_);
bb::HistoryArena arena_{g_raw, g_agg, kBaselineRawCap, kBaselineAggCap};
bb::History history_{arena_};
bb::EventLog events_;
bb::ButtonFsm button_;
bb::Config config_;
bb::UsbStatus usb_{};

uint32_t last_health_ms_ = 0;

}  // namespace

void setup() {
    pinMode(6, OUTPUT);        // PM_ENABLE (U7 ON, active-high) — default LOW: PM off
    digitalWrite(6, LOW);
    pinMode(7, OUTPUT);        // STATUS_LED_K, active-low
    digitalWrite(7, HIGH);     // LED off
    pinMode(10, INPUT_PULLUP); // USER_BUTTON_N (external R8 10k pull-up populated)
    pinMode(3, INPUT);         // REG_PG from U5

    i2c_.begin();
    uart_.begin();
    Serial.begin(115200);      // USB CDC (native USB via module USB_D+/D-)
    history_.reset_counters();
}

void loop() {
    const uint32_t now_ms = static_cast<uint32_t>(clock_.monotonic_us() / 1000ULL);

    // --- Power source classification (PWR-03 matrix) ---------------------
    const int vbus_mv = digitalRead(3) ? 5000 : 0;  // REG_PG is a presence gate, not a gauge
    const int cc1_mv = analogReadMilliVolts(0);     // CC1_SENSE divider node
    const int cc2_mv = analogReadMilliVolts(1);     // CC2_SENSE divider node
    usb_.configured = static_cast<bool>(Serial);  // CDC DTR asserted by host
    const bb::SourceState src = bb::classify_source(vbus_mv, cc1_mv, cc2_mv);
    const bb::DeviceMode mode = bb::decide_mode(src, usb_);
    digitalWrite(6, bb::pm_allowed(mode) ? HIGH : LOW);

    // --- Button (COM-06 / DAT-06 detection; actions wired in issue #7) ----
    switch (button_.update(digitalRead(10) == LOW, now_ms)) {
        case bb::ButtonAction::ShortPress:
            events_.add(clock_.monotonic_us(), 0, "short_press", 11);
            break;
        case bb::ButtonAction::SetupHold:
            events_.add(clock_.monotonic_us(), 0, "setup_hold", 10);
            break;
        case bb::ButtonAction::FactoryHold:
            events_.add(clock_.monotonic_us(), 0, "factory_hold", 12);
            history_.clear_history();
            events_.clear();
            break;
        default: break;
    }

    // --- Acquisition tick (SNS-02 bounded interval) -----------------------
    static uint32_t last_tick_ms = 0;
    const uint32_t interval = bb::validate_config(config_) == bb::ConfigError::Ok
                                  ? config_.interval_ms
                                  : bb::kDefaultIntervalMs;
    if (now_ms - last_tick_ms >= interval) {
        last_tick_ms = now_ms;
        bb::RawRecord rec{};
        sampler_.tick(now_ms, bb::pm_allowed(mode), rec);
        rec.mono_us = clock_.monotonic_us();
        rec.clock_q = bb::ClockQuality::Unset;  // wall time source lands with #7
        rec.wall_us = 0;
        history_.append(rec);
    }

    // --- Serial health stream (COM-03 fallback; 1 Hz) ---------------------
    if (now_ms - last_health_ms_ >= 1000) {
        last_health_ms_ = now_ms;
        bb::CompactRecord newest{};
        const bool have_newest = history_.newest(newest);
        bb::HealthSnapshot s{};
        s.fw_version = kFwVersion;
        s.uptime_s = now_ms / 1000U;
        s.mode = mode;
        s.source = src;
        s.raw_used = history_.raw_used();
        s.raw_capacity = history_.raw_capacity();
        s.agg_used = history_.agg_used();
        s.agg_capacity = history_.agg_capacity();
        s.oldest_seq = have_newest ? (newest.seq + 1U - history_.raw_used()) : 0;
        s.newest_seq = have_newest ? newest.seq : 0;
        s.clock_q = bb::ClockQuality::Unset;
        if (have_newest) {
            using bb::status_of_bits;
            s.pm25 = status_of_bits(newest.status, 0);
            s.voc = status_of_bits(newest.status, 1);
            s.temp = status_of_bits(newest.status, 2);
            s.rh = status_of_bits(newest.status, 3);
            s.pm25_valid = s.pm25 == bb::ChannelStatus::Ready;
            s.voc_valid = s.voc == bb::ChannelStatus::Ready;
            s.temp_valid = s.temp == bb::ChannelStatus::Ready;
            s.rh_valid = s.rh == bb::ChannelStatus::Ready;
            s.pm25_value = newest.pm25 / 100.0f;
            s.voc_raw = static_cast<float>(newest.voc);
            s.temp_value = newest.temp_c / 100.0f;
            s.rh_value = newest.rh / 100.0f;
        } else {
            s.pm25 = s.voc = s.temp = s.rh = bb::ChannelStatus::Unknown;
        }
        char line[512];
        const size_t n = bb::render_health_line(s, line, sizeof(line));
        if (n) Serial.write(line, n);
    }
}
