#include "core/power_source.h"

namespace bb {

namespace {
bool in_window(int mv, int lo, int hi) { return mv >= lo && mv <= hi; }
}

SourceState classify_source(int vbus_mv, int cc1_mv, int cc2_mv) {
    if (vbus_mv < kVbusPresentMv) return SourceState::NoVbus;
    auto win = [&](int mv) -> int {
        if (mv < 0) return -1;
        if (in_window(mv, k15aLoMv, k15aHiMv)) return 2;
        if (in_window(mv, k3aLoMv, k3aHiMv)) return 3;
        if (in_window(mv, kDefaultLoMv, kDefaultHiMv)) return 1;
        return 0;
    };
    const int w1 = win(cc1_mv), w2 = win(cc2_mv);
    // Either CC may carry the advertisement; the non-zero window wins. A
    // grounded/absent CC reads ~0 (no window). Conflict or gap -> unknown.
    if (w1 == 3 || w2 == 3) return w1 == 2 || w2 == 2 ? SourceState::UnknownCc : SourceState::Cc3A;
    if (w1 == 2 || w2 == 2) return SourceState::Cc15A;
    if (w1 == 1 || w2 == 1) return SourceState::DefaultUsbCc;
    return SourceState::UnknownCc;
}

DeviceMode decide_mode(SourceState src, const UsbStatus& usb) {
    if (usb.suspended) return DeviceMode::Suspended;
    if (usb.denied_or_droop) return DeviceMode::Error;
    if (usb.brownout_reboots >= kBrownoutLoopLimit) return DeviceMode::RecoveryOnly;
    switch (src) {
        case SourceState::Cc15A:
        case SourceState::Cc3A:
            return DeviceMode::FullSensing;
        case SourceState::DefaultUsbCc:
            return usb.configured ? DeviceMode::FullSensing : DeviceMode::RecoveryOnly;
        case SourceState::NoVbus:
        case SourceState::UnknownCc:
        default:
            return DeviceMode::RecoveryOnly;
    }
}

}  // namespace bb
