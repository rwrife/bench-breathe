// Portable sensor drivers: run the datasheet command sequences over the
// core/hal.h bus interfaces. No Arduino/ESP includes — usable natively with
// fake buses and on-device with Wire/UART implementations.
//
// Evidence boundary: these drivers are transcribed from manufacturer PDFs
// (SHT4x v6.4 §4.5/§4.6, SGP40 v1.2 §4.7/Table 8-10, SPS30 v2.0 §5.3/§6.3).
// Unit tests prove transcription against the datasheets' own worked vectors.
// Behavior on real silicon is a BENCH item pending a named prototype.
#pragma once
#include <cstdint>

#include "core/hal.h"
#include "core/sample.h"
#include "core/sht40.h"
#include "core/sgp40.h"
#include "core/sps30.h"

namespace bb {

struct Clock {
    virtual ~Clock() = default;
    virtual uint64_t monotonic_us() = 0;
    virtual void delay_ms(uint32_t ms) = 0;
};

// SHT40 driver: high-repeatability no-stretch measurement (0xFD). Datasheet
// v6.4 §3.1 timings: tMEAS,h typ 6.9 ms, max 8.3 ms -> a 12 ms wait covers
// max without relying on clock stretching.
class Sht40Driver {
public:
    Sht40Driver(I2c& i2c, Clock& clk) : i2c_(i2c), clk_(clk) {}
    bool measure(Sht40Reading& out);

private:
    I2c& i2c_;
    Clock& clk_;
};

// SGP40 driver: measure_raw_signal with RH/T compensation when the SHT40
// provides fresh values (datasheet §3.1: humidity compensation uses current
// ambient). Measurement duration typ. 25 ms, max 30 ms -> 32 ms wait.
class Sgp40Driver {
public:
    Sgp40Driver(I2c& i2c, Clock& clk) : i2c_(i2c), clk_(clk) {}
    bool measure_raw(float rh_pct, float temp_c, uint16_t& sraw_voc);

private:
    I2c& i2c_;
    Clock& clk_;
};

// SPS30 driver over UART/SHDLC: start measurement once, then poll Read
// Measured Values (1 s cadence, empty frame = no new data).
class Sps30Driver {
public:
    Sps30Driver(Uart& uart, Clock& clk) : uart_(uart), clk_(clk) {}
    bool start_measurement();
    // Poll for a new value frame; returns true and fills `out` on fresh data.
    bool poll_values(Sps30Values& out);

private:
    void pump_rx();
    Uart& uart_;
    Clock& clk_;
    bool started_ = false;
    ShdlcFrameReader reader_{};
    bool have_values_ = false;
    Sps30Values values_{};
};

// PM warm-up horizon (SNS-05): SPS30 datasheet §1/Table 1 reports stable
// output typical 8 s (low concentration) up to 30 s worst case; the driver
// reports Warming until this many ms of uptime after start, and any bus
// failure moves it to Fault.
inline constexpr uint64_t kSps30WarmingMs = 30000;
// SGP40 baseline conditioning: "reliably detecting VOC events < 60 s", full
// spec < 1 h (SGP40 Table 1). MVP surfaces Warming for the first hour and
// marks the reading a proxy (SNS-07 wording handled at the API layer).
inline constexpr uint64_t kSgp40WarmingMs = 3600000ULL;

// Per-sensor state machine combining bus results + warm-up windows.
struct PmChannel {
    ChannelStatus status = ChannelStatus::Unknown;
    uint64_t started_mono_ms = 0;
    bool has_start = false;
    float last_value = 0.0f;
    uint64_t last_ok_mono_ms = 0;
    bool has_value = false;
};

struct VocChannel {
    ChannelStatus status = ChannelStatus::Unknown;
    uint64_t started_mono_ms = 0;
    bool has_start = false;
    uint16_t last_raw = 0;
    uint64_t last_ok_mono_ms = 0;
    bool has_value = false;
};

// One acquisition tick: read SHT40 -> feed SGP40 compensation -> read SGP40;
// PM channel polled independently at its 1 s cadence. Values with slower
// cadence repeat their latest reading with retained age (SNS-02).
class Sampler {
public:
    Sampler(Sht40Driver& sht, Sgp40Driver& sgp, Sps30Driver& sps)
        : sht_(sht), sgp_(sgp), sps_(sps) {}

    // Called every tick. `now_mono_ms` monotonic. `power_allows_pm` from
    // power_source gating; when false the PM channel is PowerGated (PWR-03).
    void tick(uint64_t now_mono_ms, bool power_allows_pm, RawRecord& out);

    // SPS30 fan starts draw 80 mA max in the first 200 ms (SPS30 Table 2).
    // Gate start behind full-sensing mode and never overlap it with Wi-Fi
    // high-power TX assumptions from the component-selection static budget.
    void request_pm_start(uint64_t now_mono_ms);

    PmChannel pm;
    VocChannel voc;

private:
    Sht40Driver& sht_;
    Sgp40Driver& sgp_;
    Sps30Driver& sps_;
    bool pm_start_requested_ = false;
    bool pm_started_ = false;
    Sht40Reading out_th_{};
};

}  // namespace bb
