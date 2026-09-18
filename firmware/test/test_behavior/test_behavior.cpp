// Behavior tests over fake buses: sampler sequencing, power gating, button
// FSM, and config validation. These prove *logic and sequencing*, driven by
// the same fakes the device drivers use — still static/simulation evidence,
// never bench.
#include <unity.h>

#include <cmath>
#include <cstring>

#include "core/button.h"
#include "core/config.h"
#include "core/power_source.h"
#include "core/sensors.h"
#include "core/shdlc_vectors.h"
#include "hal/host_sim.h"

using namespace bb;

void setUp(void) {}
void tearDown(void) {}

static void test_config_bounds_reject_not_clamp(void) {
    // SNS-03: invalid intervals are rejected, not silently clamped.
    Config c{};
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ConfigError::Ok),
                            static_cast<uint8_t>(validate_config(c)));
    c.interval_ms = 1999;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ConfigError::IntervalOutOfRange),
                            static_cast<uint8_t>(validate_config(c)));
    c.interval_ms = 60001;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ConfigError::IntervalOutOfRange),
                            static_cast<uint8_t>(validate_config(c)));
    c.interval_ms = kIntervalMinMs;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ConfigError::Ok),
                            static_cast<uint8_t>(validate_config(c)));
    c.interval_ms = kIntervalMaxMs;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ConfigError::Ok),
                            static_cast<uint8_t>(validate_config(c)));
}

static void test_label_bound(void) {
    Config c{};
    char big[kLabelMaxLen + 2];
    memset(big, 'a', sizeof(big));
    TEST_ASSERT_FALSE(set_label(c, big, kLabelMaxLen + 1));   // too long -> rejected
    TEST_ASSERT_TRUE(set_label(c, big, kLabelMaxLen));        // fits exactly
    TEST_ASSERT_EQUAL_UINT(kLabelMaxLen, strlen(c.label));
}

static void test_button_windows(void) {
    // Drive the FSM the way the main loop does: repeated polls at ~1 kHz.
    // expect_actions = how many actions should fire across the phase.
    auto drive = [](ButtonFsm& fsm, bool pressed, uint64_t t0, uint64_t t1, int expect_actions) {
        ButtonAction out = ButtonAction::None;
        int count = 0;
        for (uint64_t t = t0; t <= t1; t += 5) {
            const ButtonAction a = fsm.update(pressed, t);
            if (a != ButtonAction::None) { out = a; count++; }
        }
        TEST_ASSERT_EQUAL_INT(expect_actions, count);  // never double-fire
        return out;
    };

    {
        ButtonFsm fsm;
        drive(fsm, true, 0, 100, 0);
        TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ButtonAction::ShortPress),
                                static_cast<uint8_t>(drive(fsm, false, 105, 400, 1)));
    }
    {
        // 10 ms bounce inside a 150 ms press: still exactly one ShortPress,
        // and it must not read as a setup hold.
        ButtonFsm fsm;
        drive(fsm, true, 0, 40, 0);
        drive(fsm, false, 45, 50, 0);
        drive(fsm, true, 55, 150, 0);
        TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ButtonAction::ShortPress),
                                static_cast<uint8_t>(drive(fsm, false, 155, 500, 1)));
    }
    {
        ButtonFsm fsm;
        drive(fsm, true, 0, 6000, 0);
        TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ButtonAction::SetupHold),
                                static_cast<uint8_t>(drive(fsm, false, 6005, 6300, 1)));
    }
    {
        ButtonFsm fsm;
        drive(fsm, true, 0, 20000, 0);
        TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ButtonAction::FactoryHold),
                                static_cast<uint8_t>(drive(fsm, false, 20005, 20300, 1)));
    }
    {
        // ~1 s press stays ShortPress (no accidental setup).
        ButtonFsm fsm;
        drive(fsm, true, 0, 1000, 0);
        TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ButtonAction::ShortPress),
                                static_cast<uint8_t>(drive(fsm, false, 1005, 1300, 1)));
    }
}

static void test_power_matrix(void) {
    // Source-state matrix rows from hardware/requirements.md §2.
    UsbStatus usb{};
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::RecoveryOnly),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 280, -1), usb)));  // default CC, unconfigured
    usb.configured = true;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::FullSensing),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 280, -1), usb)));  // configured 500 mA
    usb.configured = false;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::FullSensing),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 1000, -1), usb)));  // CC 1.5 A
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::FullSensing),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, -1, 2100), usb)));  // CC 3 A (either pin)
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::RecoveryOnly),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 700, -1), usb)));   // gap -> unknown CC
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::Suspended),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 280, -1), UsbStatus{.suspended = true})));
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::Error),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 1000, -1), UsbStatus{.denied_or_droop = true})));
    // Brownout loop guard: repeated brownouts pin to RecoveryOnly even on 1.5 A CC.
    UsbStatus bo{};
    bo.brownout_reboots = kBrownoutLoopLimit;
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(DeviceMode::RecoveryOnly),
                            static_cast<uint8_t>(decide_mode(classify_source(5000, 1000, -1), bo)));
    // No VBUS -> recovery regardless.
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(SourceState::NoVbus),
                            static_cast<uint8_t>(classify_source(0, 1000, 1000)));
    TEST_ASSERT_FALSE(pm_allowed(DeviceMode::RecoveryOnly));
    TEST_ASSERT_FALSE(wifi_allowed(DeviceMode::RecoveryOnly));
    TEST_ASSERT_TRUE(pm_allowed(DeviceMode::FullSensing));
}

static void test_sampler_full_pipeline_with_fakes(void) {
    sim::FakeClock clk;
    sim::FakeI2c i2c;
    sim::FakeUart uart;
    // Program fakes: SHT40 T=25°C(0x6666-ish) RH=50%, SGP40 raw=32000.
    // T ticks for 25 °C: (25+45)*65535/175 = 26214 = 0x6666.
    i2c.set_response(kSht40Address, sim::sht40_response(0x6666, 0x6666));
    i2c.set_response(kSgp40Address, sim::sgp40_response(32000));
    Sht40Driver sht(i2c, clk);
    Sgp40Driver sgp(i2c, clk);
    Sps30Driver sps(uart, clk);
    Sampler sampler(sht, sgp, sps);

    // Tick 1 with PM NOT allowed: PM must be null with PowerGated reason,
    // SHT/SGP exercised, SGP warming (first sample).
    RawRecord rec{};
    sampler.tick(1000, /*power_allows_pm=*/false, rec);
    TEST_ASSERT_TRUE(rec.temp_c.valid);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 25.0f, rec.temp_c.value);
    TEST_ASSERT_TRUE(rec.rh.valid);
    TEST_ASSERT_TRUE(rec.voc.valid);
    TEST_ASSERT_EQUAL_UINT16(32000, static_cast<uint16_t>(rec.voc.value));
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ChannelStatus::Warming), static_cast<uint8_t>(rec.voc.status));
    TEST_ASSERT_FALSE(rec.pm25.valid);
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(NullReason::PowerGated), static_cast<uint8_t>(rec.pm25.reason));
    // UART must have stayed silent (PWR-03: PM off outside full-sensing).
    TEST_ASSERT_EQUAL_UINT(0u, static_cast<unsigned>(uart.tx_seen.size()));

    // Tick with PM allowed: driver starts measurement (SHDLC start frame on TX).
    sampler.request_pm_start(2000);
    RawRecord rec2{};
    sampler.tick(2000, true, rec2);
    TEST_ASSERT_TRUE(uart.tx_seen.size() >= 8);  // start frame went out
    // No response queued -> pm25 not yet valid, Warming/NotYetMeasured.
    TEST_ASSERT_FALSE(rec2.pm25.valid);

    // Queue a values frame and poll: PM2.5 = 12.5 µg/m³ (frame checksummed
    // per §5.2, stuffed per Table 5 by shdlc_vectors).
    uart.queue_rx(sps30_test_values_frame_pm25(12.5f));
    // Refresh i2c responses for next tick.
    i2c.set_response(kSht40Address, sim::sht40_response(0x6666, 0x6666));
    i2c.set_response(kSgp40Address, sim::sgp40_response(32000));
    RawRecord rec3{};
    sampler.tick(4000, true, rec3);
    TEST_ASSERT_TRUE(rec3.pm25.valid);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 12.5f, rec3.pm25.value);
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ChannelStatus::Warming), static_cast<uint8_t>(rec3.pm25.status));

    // Advance past the 30 s warm-up horizon with continued reads -> Ready.
    // The tick clock here is the fake clock timeline, which started near 0
    // and lags the explicit tick timestamps; advance generously (40 s) so
    // elapsed-since-start (≈2 s on that timeline) exceeds kSps30WarmingMs.
    clk.advance_ms(kSps30WarmingMs + 40000);
    uart.queue_rx(sps30_test_values_frame_pm25(12.5f));
    i2c.set_response(kSht40Address, sim::sht40_response(0x6666, 0x6666));
    i2c.set_response(kSgp40Address, sim::sgp40_response(32000));
    RawRecord rec4{};
    sampler.tick(clk.monotonic_us() / 1000ULL, true, rec4);
    TEST_ASSERT_TRUE(rec4.pm25.valid);
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ChannelStatus::Ready), static_cast<uint8_t>(rec4.pm25.status));
}

static void test_sampler_bus_fault_marks_fault(void) {
    sim::FakeClock clk;
    sim::FakeI2c i2c;
    sim::FakeUart uart;
    i2c.set_nack(kSht40Address, true);   // SHT40 absent/faulted
    i2c.set_response(kSgp40Address, sim::sgp40_response(30000));
    Sht40Driver sht(i2c, clk);
    Sgp40Driver sgp(i2c, clk);
    Sps30Driver sps(uart, clk);
    Sampler sampler(sht, sgp, sps);
    RawRecord rec{};
    sampler.tick(1000, true, rec);
    TEST_ASSERT_FALSE(rec.temp_c.valid);
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(ChannelStatus::Fault), static_cast<uint8_t>(rec.temp_c.status));
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(NullReason::SensorFault), static_cast<uint8_t>(rec.temp_c.reason));
    // SGP40 used default compensation words when SHT40 failed: write frame
    // must carry the Table-9 defaults.
    TEST_ASSERT_EQUAL_UINT8(0x26, i2c.last_write[0]);
    TEST_ASSERT_EQUAL_UINT8(0x0F, i2c.last_write[1]);
    TEST_ASSERT_EQUAL_UINT8(0x80, i2c.last_write[2]);
    TEST_ASSERT_EQUAL_UINT8(0x00, i2c.last_write[3]);
    TEST_ASSERT_EQUAL_UINT8(0xA2, i2c.last_write[4]);
    TEST_ASSERT_EQUAL_UINT8(0x66, i2c.last_write[5]);
    TEST_ASSERT_EQUAL_UINT8(0x66, i2c.last_write[6]);
    TEST_ASSERT_EQUAL_UINT8(0x93, i2c.last_write[7]);
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_config_bounds_reject_not_clamp);
    RUN_TEST(test_label_bound);
    RUN_TEST(test_button_windows);
    RUN_TEST(test_power_matrix);
    RUN_TEST(test_sampler_full_pipeline_with_fakes);
    RUN_TEST(test_sampler_bus_fault_marks_fault);
    return UNITY_END();
}
