// USB source-state classification and mode gating (PWR-03, source-state
// matrix in hardware/requirements.md §2). Pure logic — the device HAL feeds
// CC divider voltages (ADC on GPIO0/GPIO1, nets CC1_SENSE/CC2_SENSE) and USB
// enumeration status; tests run identical code natively.
//
// CC voltage windows are the USB Type-C specification's sink-side
// advertisement windows for an Rd (5.1 kΩ) sink, as transcribed in the
// project's static review (TI/ST Type-C application notes; exact spec table
// citation is a bench-time evidence item — see firmware/README.md). The
// classifier is deliberately conservative: anything outside a narrow,
// non-overlapping window classifies as UnknownCc, which may never enter
// FullSensing.
//
// Matrix (requirements.md):
//   CC 1.5 A or 3 A advertisement          -> FullSensing allowed (500 mA peak)
//   USB2 host, before configuration        -> RecoveryOnly   (100 mA)
//   USB2 host configured for 500 mA        -> FullSensing allowed (500 mA peak)
//   USB suspend                            -> Suspended      (2.5 mA)
//   unknown/default CC w/o configuration,
//   denied config, detected droop          -> RecoveryOnly   (100 mA), no brownout loop
#pragma once
#include <cstdint>

namespace bb {

enum class SourceState : uint8_t {
    NoVbus = 0,        // VBUS sense low (REG_PG/GPIO; treated as host-uncharged)
    DefaultUsbCc,      // CC in default-USB window; needs host configuration for full sensing
    Cc15A,             // CC advertises 1.5 A
    Cc3A,              // CC advertises 3.0 A
    UnknownCc,         // outside windows / charge-only / legacy cable
};

enum class DeviceMode : uint8_t {
    RecoveryOnly = 0,  // serial + health only; PM and Wi-Fi OFF (100 mA ceiling)
    FullSensing,       // sensors + Wi-Fi permitted (500 mA ceiling)
    Suspended,         // radio + sensors off; wake on resume
    Error,             // droop/denied: like RecoveryOnly + insufficient-power flag
};

// Millivolt windows (mV). Gap between windows classifies as UnknownCc.
inline constexpr int kDefaultLoMv = 200, kDefaultHiMv = 380;
inline constexpr int k15aLoMv = 850, k15aHiMv = 1350;
inline constexpr int k3aLoMv = 1650, k3aHiMv = 2650;
inline constexpr int kVbusPresentMv = 3500;  // 5 V rail present threshold (3.5 V)

// Classify from the highest valid CC reading (either CC may advertise).
// cc_mv values are the ADC-measured divider node voltages; -1 = not measured.
SourceState classify_source(int vbus_mv, int cc1_mv, int cc2_mv);

struct UsbStatus {
    bool configured = false;   // USB enumeration completed (host granted load)
    bool suspended = false;    // USB suspend detected
    bool denied_or_droop = false;  // config denied or source droop observed
    uint32_t brownout_reboots = 0; // persisted count since last successful full run
};

inline constexpr uint32_t kBrownoutLoopLimit = 3;  // repeated brownouts -> stay RecoveryOnly

// The mode gate. FullSensing requires a permissive source AND a configured
// or high-current-CC source AND no droop history AND no brownout loop.
DeviceMode decide_mode(SourceState src, const UsbStatus& usb);

// True when heavy loads (PM fan, Wi-Fi TX) must be suppressed in this mode.
inline bool pm_allowed(DeviceMode m) { return m == DeviceMode::FullSensing; }
inline bool wifi_allowed(DeviceMode m) { return m == DeviceMode::FullSensing; }

}  // namespace bb
