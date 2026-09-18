// Button behaviour (COM-06, DAT-06): one physical button distinguishes
//   - short press            -> event marker opportunity
//   - sustained >= 5 s       -> begin setup mode (single action, visible)
//   - sustained >= 15 s      -> begin factory reset (sustained action, app cannot trigger)
// All thresholds are enforced as hold *windows* evaluated on release, so a
// reset only fires on release-after-hold, never mid-hold (avoids accidental
// completion during handling). Bounded debounce matches the hardware RC (C9).
#pragma once
#include <cstdint>

namespace bb {

inline constexpr uint64_t kDebounceMs = 30;      // > RC debounce (~C9/R8); software backstop
inline constexpr uint64_t kSetupHoldMs = 5000;   // COM-06 sustained action
inline constexpr uint64_t kFactoryHoldMs = 15000;// DAT-06 sustained action, longer than setup

enum class ButtonAction : uint8_t {
    None = 0,
    ShortPress,
    SetupHold,      // released between 5 s and 15 s hold
    FactoryHold,    // released at/after 15 s hold
};

class ButtonFsm {
public:
    // Feed the raw active-low net state (true = pressed, USER_BUTTON_N low).
    // `now_ms` is monotonic and must be called repeatedly (the main loop).
    // A state change commits only after kDebounceMs of stable samples; the
    // hold window is measured edge-to-edge (press edge -> release edge), so
    // a reset only fires on release-after-hold, never mid-hold.
    ButtonAction update(bool raw_pressed, uint64_t now_ms) {
        ButtonAction action = ButtonAction::None;
        if (raw_pressed != last_raw_) {
            last_raw_ = raw_pressed;
            edge_ms_ = now_ms;
        }
        const bool stable = (now_ms - edge_ms_) >= kDebounceMs;
        if (stable && last_raw_ && !pressed_) {
            pressed_ = true;
            press_start_ms_ = edge_ms_;
        } else if (stable && !last_raw_ && pressed_) {
            pressed_ = false;
            const uint64_t held = edge_ms_ - press_start_ms_;
            if (held >= kFactoryHoldMs) action = ButtonAction::FactoryHold;
            else if (held >= kSetupHoldMs) action = ButtonAction::SetupHold;
            else if (held >= kDebounceMs) action = ButtonAction::ShortPress;
        }
        return action;
    }

    bool pressed() const { return pressed_; }

private:
    bool last_raw_ = false;
    uint64_t edge_ms_ = 0;
    bool pressed_ = false;
    uint64_t press_start_ms_ = 0;
};

}  // namespace bb
