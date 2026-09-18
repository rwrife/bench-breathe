// Codec tests against manufacturer-datasheet worked vectors ONLY — these
// prove transcription, not bench behavior. Sources:
//   SHT4x v6.4 §4.4 Table 7: CRC(0xBEEF) = 0x92; §4.5 Table 8 command bytes;
//     §4.6 conversion equations (pseudocode listing t=-45+175*ticks/65535,
//     rh=-6+125*rh/65535 clamped).
//   SGP40 v1.2 Table 10: default words 0x8000+0xA2 (RH 50%), 0x6666+0x93
//     (T 25 °C); min/max words 0x0000+0x81 and 0xFFFF+0xAC.
//   SPS30 v2.0 §5.2: checksum example 0x00 0x00 0x02 0x01 0x03 -> 0xF9;
//     §5.3.1 start frame 7E 00 00 02 01 03 F9 7E; §5.3.3 read frame
//     7E 00 03 00 FC 7E and empty response 7E 00 03 00 00 FC 7E;
//     Table 5 byte-stuffing example [0x43,0x11,0x7F] -> [0x43,0x7D,0x31,0x7F].
#include <unity.h>

#include <cmath>
#include <cstring>
#include <vector>

#include "core/crc8_sensirion.h"
#include "core/health_line.h"
#include "core/history.h"
#include "core/sgp40.h"
#include "core/shdlc_vectors.h"
#include "core/sht40.h"
#include "core/sps30.h"

using namespace bb;

void setUp(void) {}
void tearDown(void) {}

static void test_crc_vectors(void) {
    // SHT4x Table 7 canonical vector
    const uint8_t beef[2] = {0xBE, 0xEF};
    TEST_ASSERT_EQUAL_HEX8(0x92, sensirion_crc8(beef, 2));
    // SGP40 Table 10 vectors (also SHT40-style per-word CRC)
    TEST_ASSERT_EQUAL_HEX8(0xA2, sensirion_crc8_u16(0x8000));
    TEST_ASSERT_EQUAL_HEX8(0x93, sensirion_crc8_u16(0x6666));
    TEST_ASSERT_EQUAL_HEX8(0x81, sensirion_crc8_u16(0x0000));
    TEST_ASSERT_EQUAL_HEX8(0xAC, sensirion_crc8_u16(0xFFFF));
}

static void test_sht40_conversion(void) {
    // §4.6: T = -45 + 175*St/65535; RH = -6 + 125*Srh/65535 clamped [0,100].
    Sht40Reading r = sht40_ticks_to_reading(0x4000, 0x6666);
    // Hand-computed: 0x4000=16384 -> -45 + 175*16384/65535 = -45 + 43.7507 = -1.2493
    TEST_ASSERT_FLOAT_WITHIN(0.002f, -1.2493f, r.temp_c);
    // 0x6666=26214; 125*26214 = 3,276,750 = exactly 50*65535 -> RH = 44.0000
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 44.0f, r.rh_pct);

    // Clamping: 0 -> -6 clamps to 0; 0xFFFF -> 119 clamps to 100.
    r = sht40_ticks_to_reading(0, 0);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, r.rh_pct);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, -45.0f, r.temp_c);
    r = sht40_ticks_to_reading(0xFFFF, 0xFFFF);
    TEST_ASSERT_EQUAL_FLOAT(100.0f, r.rh_pct);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 130.0f, r.temp_c);
}

static void test_sht40_decode_crc_fail(void) {
    uint8_t resp[6];
    sensirion_encode_u16(0x4000, resp);
    sensirion_encode_u16(0x6666, resp + 3);
    Sht40Reading r{};
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(Sht40Error::Ok),
                            static_cast<uint8_t>(sht40_decode_measurement(resp, r)));
    resp[5] ^= 0xFF;  // corrupt CRC
    TEST_ASSERT_EQUAL_UINT8(static_cast<uint8_t>(Sht40Error::CrcMismatch),
                            static_cast<uint8_t>(sht40_decode_measurement(resp, r)));
}

static void test_sgp40_frame_vectors(void) {
    // SGP40 Table 9 exact default frame (uncompensated).
    uint8_t frame[8];
    size_t len = sgp40_build_measure_frame(NAN, NAN, frame);
    TEST_ASSERT_EQUAL_UINT(static_cast<unsigned>(8), static_cast<unsigned>(len));
    const uint8_t expect[8] = {0x26, 0x0F, 0x80, 0x00, 0xA2, 0x66, 0x66, 0x93};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(expect, frame, 8);

    // Table 10: RH=0 -> 0x0000+0x81, T=-45 -> 0x0000+0x81.
    len = sgp40_build_measure_frame(0.0f, -45.0f, frame);
    const uint8_t lo[8] = {0x26, 0x0F, 0x00, 0x00, 0x81, 0x00, 0x00, 0x81};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(lo, frame, 8);

    // RH=100 / T=130 -> 0xFFFF+0xAC.
    len = sgp40_build_measure_frame(100.0f, 130.0f, frame);
    const uint8_t hi[8] = {0x26, 0x0F, 0xFF, 0xFF, 0xAC, 0xFF, 0xFF, 0xAC};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(hi, frame, 8);
}

static void test_sgp40_decode(void) {
    uint8_t resp[3];
    sensirion_encode_u16(0x1234, resp);
    TEST_ASSERT_EQUAL_INT32(0x1234, sgp40_decode_raw_response(resp));
    resp[2] ^= 0x01;
    TEST_ASSERT_EQUAL_INT32(-1, sgp40_decode_raw_response(resp));
}

static void test_sps30_checksum_and_frames(void) {
    // §5.2 worked example (before stuffing): ADR CMD L DATA... -> CHK 0xF9
    const uint8_t pre[] = {0x00, 0x00, 0x02, 0x01, 0x03};
    TEST_ASSERT_EQUAL_HEX8(0xF9, shdlc_checksum(pre, 5));

    // §5.3.1 exact frame from datasheet example.
    uint8_t f[8];
    TEST_ASSERT_EQUAL_UINT(static_cast<unsigned>(8), static_cast<unsigned>(sps30_frame_start_measurement(f)));
    const uint8_t start[8] = {0x7E, 0x00, 0x00, 0x02, 0x01, 0x03, 0xF9, 0x7E};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(start, f, 8);

    // §5.3.3 read-values frame.
    uint8_t r[6];
    sps30_frame_read_values(r);
    const uint8_t read[6] = {0x7E, 0x00, 0x03, 0x00, 0xFC, 0x7E};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(read, r, 6);
}

static void test_sps30_stuffing(void) {
    // §5.2 Table 5 example: [0x43,0x11,0x7F] -> [0x43,0x7D,0x31,0x7F].
    const uint8_t in[] = {0x43, 0x11, 0x7F};
    uint8_t out[8];
    TEST_ASSERT_EQUAL_UINT(4u, static_cast<unsigned>(shdlc_stuff(in, 3, out, sizeof(out))));
    const uint8_t want[] = {0x43, 0x7D, 0x31, 0x7F};
    TEST_ASSERT_EQUAL_UINT8_ARRAY(want, out, 4);
}

static void test_sps30_reader_empty_response(void) {
    // §5.3.3 empty response frame: 7E 00 03 00 00 FC 7E
    const uint8_t frame[] = {0x7E, 0x00, 0x03, 0x00, 0x00, 0xFC, 0x7E};
    ShdlcFrameReader reader;
    for (uint8_t b : frame) reader.feed(b);
    TEST_ASSERT_TRUE(reader.complete());
    TEST_ASSERT_EQUAL_HEX8(0x03, reader.command());
    TEST_ASSERT_EQUAL_HEX8(0x00, reader.state());
    TEST_ASSERT_TRUE(reader.checksum_ok());
    TEST_ASSERT_EQUAL_UINT(static_cast<unsigned>(0), static_cast<unsigned>(reader.data_len()));
}

static void test_sps30_reader_values_response(void) {
    // Datasheet §5.3.3 example response (all-zero payload, CHK 0xD4):
    // 7E 00 03 00 28 <40 zero bytes> D4 7E
    std::vector<uint8_t> frame = sps30_test_values_frame_zeroed();
    ShdlcFrameReader reader;
    for (uint8_t b : frame) reader.feed(b);
    TEST_ASSERT_TRUE(reader.complete());
    TEST_ASSERT_TRUE(reader.checksum_ok());
    TEST_ASSERT_EQUAL_UINT(static_cast<unsigned>(40), static_cast<unsigned>(reader.data_len()));
    Sps30Values v{};
    TEST_ASSERT_TRUE(sps30_decode_values(reader.data(), reader.data_len(), v));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, v.pm2_5);
}

static void test_sps30_reader_rejects_bad_checksum(void) {
    const uint8_t frame[] = {0x7E, 0x00, 0x03, 0x00, 0x00, 0x00, 0x7E};  // CHK wrong
    ShdlcFrameReader reader;
    for (uint8_t b : frame) reader.feed(b);
    TEST_ASSERT_TRUE(reader.complete());
    TEST_ASSERT_FALSE(reader.checksum_ok());
}

static void test_history_rollover_and_publish(void) {
    // Small arena exercises rollover + aggregate publish deterministically.
    static CompactRecord raw[4];
    static AggCompact agg[2];
    HistoryArena arena{raw, agg, 4, 2};
    History h(arena);
    h.reset_counters();

    for (uint32_t i = 0; i < 10; ++i) {
        RawRecord r{};
        r.mono_us = i * 2000000ULL;
        r.pm25.valid = true;
        r.pm25.value = 10.0f + static_cast<float>(i);
        r.pm25.status = ChannelStatus::Ready;
        r.temp_c.valid = true;
        r.temp_c.value = 25.0f;
        r.temp_c.status = ChannelStatus::Ready;
        h.append(r);
    }
    // DAT-03: capacity used, oldest-first kept (seq 7..10 survive).
    TEST_ASSERT_EQUAL_UINT32(4, h.raw_used());
    CompactRecord oldest{}, newest{};
    TEST_ASSERT_TRUE(h.oldest(oldest));
    TEST_ASSERT_TRUE(h.newest(newest));
    TEST_ASSERT_EQUAL_UINT32(7, oldest.seq);
    TEST_ASSERT_EQUAL_UINT32(10, newest.seq);

    // DAT-02: all samples fold into one no-clock bucket keyed 0 -> only
    // published when the store is replaced/cleared; check via header carry.
    uint8_t hdr[128];
    h.save_header(hdr, sizeof(hdr));
    History h2(arena);
    TEST_ASSERT_TRUE(h2.load_header(hdr, sizeof(hdr)));
    TEST_ASSERT_EQUAL_UINT32(4, h2.raw_used());
    CompactRecord o2{}, n2{};
    TEST_ASSERT_TRUE(h2.oldest(o2));
    TEST_ASSERT_EQUAL_UINT32(7, o2.seq);
}

static void test_history_wall_base_freeze(void) {
    // SNS-06: clock correction must not reorder stored samples; pre-clock
    // records keep kNoWall after a later record stamps the base.
    static CompactRecord raw[8];
    static AggCompact agg[4];
    HistoryArena arena{raw, agg, 8, 4};
    History h(arena);
    h.reset_counters();

    RawRecord a{};
    a.mono_us = 1000000;
    a.pm25.valid = true; a.pm25.value = 1.0f; a.pm25.status = ChannelStatus::Ready;
    h.append(a);  // no clock yet

    RawRecord b{};
    b.mono_us = 2000000;
    b.clock_q = ClockQuality::Estimated;
    b.wall_us = 1700000000000000LL;
    b.pm25.valid = true; b.pm25.value = 2.0f; b.pm25.status = ChannelStatus::Ready;
    h.append(b);

    CompactRecord r0{}, r1{};
    TEST_ASSERT_EQUAL_UINT32(1, h.read_raw(0, &r0, 1));  // record 0 readable
    TEST_ASSERT_EQUAL_UINT32(1, h.read_raw(1, &r1, 1));  // record 1 readable
    TEST_ASSERT_EQUAL_INT32(kNoWall, r0.wall_off_s);   // stored before clock
    TEST_ASSERT_EQUAL_INT32(0, r1.wall_off_s);          // base == this record
    TEST_ASSERT_TRUE(r0.seq < r1.seq);                  // ordering preserved
}

static void test_health_line_rendering(void) {
    HealthSnapshot s{};
    s.fw_version = "0.1.0-baseline";
    s.uptime_s = 123;
    s.mode = DeviceMode::FullSensing;
    s.source = SourceState::Cc15A;
    s.raw_used = 60; s.raw_capacity = 4096; s.agg_used = 0; s.agg_capacity = 288;
    s.oldest_seq = 1; s.newest_seq = 60;
    s.clock_q = ClockQuality::Unset;
    s.pm25 = ChannelStatus::Ready; s.pm25_valid = true; s.pm25_value = 12.34f;
    s.voc = ChannelStatus::Warming; s.voc_valid = false;
    s.temp = ChannelStatus::Ready; s.temp_valid = true; s.temp_value = 25.5f;
    s.rh = ChannelStatus::Ready; s.rh_valid = true; s.rh_value = 48.0f;

    char buf[512];
    size_t n = render_health_line(s, buf, sizeof(buf));
    TEST_ASSERT_TRUE(n > 0);
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"fw\":\"0.1.0-baseline\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"mode\":\"full\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"source\":\"cc_1a5\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"status\":\"ready\",\"value\":12.34"));
    // SNS-04: invalid channel is explicit null, never zero-as-data.
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"voc_raw\":{\"status\":\"warming\",\"value\":null"));

    // Refuses to truncate when buffer is too small.
    char tiny[16];
    TEST_ASSERT_EQUAL_UINT(0u, static_cast<unsigned>(render_health_line(s, tiny, sizeof(tiny))));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_crc_vectors);
    RUN_TEST(test_sht40_conversion);
    RUN_TEST(test_sht40_decode_crc_fail);
    RUN_TEST(test_sgp40_frame_vectors);
    RUN_TEST(test_sgp40_decode);
    RUN_TEST(test_sps30_checksum_and_frames);
    RUN_TEST(test_sps30_stuffing);
    RUN_TEST(test_sps30_reader_empty_response);
    RUN_TEST(test_sps30_reader_values_response);
    RUN_TEST(test_sps30_reader_rejects_bad_checksum);
    RUN_TEST(test_history_rollover_and_publish);
    RUN_TEST(test_history_wall_base_freeze);
    RUN_TEST(test_health_line_rendering);
    return UNITY_END();
}
