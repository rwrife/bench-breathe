#!/usr/bin/env python3
"""Write the bench-breathe KiCad project file (.kicad_pro) with explicit design
rules and net classes.

An empty project container makes kicad-cli fall back to built-in defaults, so
the DRC constraints would not be reproducible from the repo. This script
commits the intended rules instead. Documented rule choices:

- min_through_hole_diameter 0.2 mm: the RF_Module:ESP32-C3-WROOM-02 heat-sink
  pad array and the WSON-8 thermal-via footprint ship 0.2 mm drills as the
  manufacturer land pattern; 0.2 mm is within standard fab capability.
- All other minimums are the conservative two-layer defaults.
- Power net class: 0.4 mm tracks for VBUS / fused input / SW_NODE / PM_5V /
  3V3 rails. USB net class: 0.25 mm (0.2 clearance) on the four USB diff
  segments between J1 and U1 via the ESD array and series 0 ohm links.

Usage: python3 make_project_settings.py <out.kicad_pro>
"""
import json
import sys


def main(out_path: str) -> int:
    power_nets = ["/VBUS", "/VBUS_FUSED", "/SW_NODE", "/PM_5V", "/+3V3"]
    usb_nets = ["/USB_DP", "/USB_DM", "/USB_CONN_DP", "/USB_CONN_DM"]

    def cls(name, track, clearance, width=0.6, drill=0.3):
        return {
            "bus_width": 12,
            "clearance": clearance,
            "diff_pair_gap": 0.1524,
            "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.127,
            "line_style": 0,
            "microvia_diameter": 0.3,
            "microvia_drill": 0.1,
            "name": name,
            "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)",
            "track_width": track,
            "via_diameter": width,
            "via_drill": drill,
            "wire_width": 6,
        }

    proj = {
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.05,
                    "copper_line_width": 0.2,
                    "courtyard_line_width": 0.05,
                    "fab_line_width": 0.1,
                    "silk_line_width": 0.15,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "rule_severities": {
                    "courtyards_overlap": "error",
                    "clearance": "error",
                    "create_first_own_package": "error",
                    "copper_edge_clearance": "error",
                    "hole_clearance": "error",
                    "hole_near_hole": "error",
                    "items_on_disabled_layers": "error",
                    "items_not_allowed": "error",
                    "lib_footprint_mismatch": "warning",
                    "silk_edge_clearance": "warning",
                    "silk_over_copper": "warning",
                    "silk_overlap": "warning",
                    "skew_out_of_range": "error",
                    "starved_terminal": "error",
                    "track_dangling": "warning",
                    "track_min_width": "warning",
                    "unconnected_items": "error",
                    "unresolved_netclass": "error",
                    "via_dangling": "warning",
                },
                "rules": {
                    "max_error": 0.005,
                    "min_clearance": 0.2,
                    "min_connection": 0.0,
                    "min_copper_edge_clearance": 0.5,
                    "min_groove_width": 0.0,
                    "min_hole_clearance": 0.25,
                    "min_hole_to_hole": 0.25,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_resolved_spokes": 2,
                    "min_silk_clearance": 0.2,
                    "min_text_height": 0.8,
                    "min_text_thickness": 0.1,
                    "min_through_hole_diameter": 0.2,
                    "min_track_width": 0.2,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.6,
                    "solder_mask_to_copper_clearance": 0.0,
                    "use_height_for_length_calcs": True,
                },
                "teardrop_options": [
                    {"onrest": False, "onshape": False, "ontest": False, "prLayer": True,
                     "prMinWidth": 0.0, "prSize": 0.3, "prUseNative": True},
                ],
                "teardrop_parameters": [
                    {"allow_use_native_teardrops": True, "enable_on_ports": False,
                     "enable_on_vias": False, "min_width": 0.0, "profile": 1,
                     "size_ratio": 0.25, "skip_small_segments": False, "target_width": 0.0,
                     "use_dynamic_limited_length": False, "use_mitered_appended_segment": False},
                ],
                "track_widths": [0.0, 0.2, 0.25, 0.4],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                   {"diameter": 0.6, "drill": 0.3},
                                   {"diameter": 0.7, "drill": 0.3}],
                "zones_allow_external_fillets": False,
            },
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "libraries": {
            "fp": {"prop": {"version": 1}},
            "ppad3d": {"prop": {"version": 1}},
            "sym": {"prop": {"version": 1}},
        },
        "net_settings": {
            "classes": [
                cls("Default", 0.2, 0.2),
                cls("Power", 0.4, 0.2),
                cls("USB", 0.25, 0.2),
            ],
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [
                ["Power", power_nets],
                ["USB", usb_nets],
            ],
        },
        "pcbnew": {
            "last_paths": {
                "gencad": "",
                "idf": "",
                "netlist": "",
                "plot": "",
                "pos_files": "",
                "specctra_dsn": "reports/",
                "step": "",
                "svg": "",
                "vrml": "",
            },
            "page_layout_descr_file": "",
        },
        "schematic": {
            "breakout_dimension": 4.0,
            "default_font": "KiCad Font",
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
            "meta": {"version": 1},
            "net_format_name": "",
            "ngspice_fixed_domain_path": "",
            "page_layout_file": "",
            "space_pin_origin": 0.254,
            "use_database": True,
            "version": 10,
            "worksheet_shape": "",
        },
        "text_variables": {},
    }
    json.dump(proj, open(out_path, "w"), indent=2)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
