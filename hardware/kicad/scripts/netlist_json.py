#!/usr/bin/env python3
"""Convert a KiCad 9 kicadsexpr netlist to a JSON pin map.

Usage: python3 netlist_json.py <netlist.net> <out.json>

Output shape: {"nets": {net_name: [[ref, pin], ...]}, "components": {ref: footprint}}
Net names keep the leading '/' as exported. All netlist values are quoted in
KiCad 9 (unquoted regexes silently match zero nets), so the patterns below
require the quotes.
"""
import json
import re
import sys


def main(net_path: str, out_path: str) -> int:
    text = open(net_path, encoding="utf-8").read()

    comps: dict[str, str] = {}
    for block in re.split(r'(?=\(comp \(ref ")', text):
        m = re.match(r'\(comp \(ref "(.*?)"\)\s*\(value "(.*?)"\)\s*\(footprint "(.*?)"\)', block, re.S)
        if m and m.group(3):  # empty footprint = off-board model, not placed
            comps[m.group(1)] = m.group(3)

    nets: dict[str, list[list[str]]] = {}
    # Split on each (net (code "N") entry; each block runs until the next entry.
    blocks = re.split(r'(?=\(net \(code "\d+"\))', text)
    for block in blocks:
        head = re.match(r'\(net \(code "\d+"\) \(name "(.*?)"\)', block)
        if not head:
            continue
        name = head.group(1)
        nodes = re.findall(r'\(node \(ref "(.*?)"\) \(pin "(.*?)"\)', block)
        nets.setdefault(name, []).extend([list(n) for n in nodes])

    # Nets may span multiple (net ...) entries with the same name; merge above.
    json.dump({"nets": nets, "components": comps}, open(out_path, "w"), indent=1)
    print(f"{len(nets)} nets, {len(comps)} footprinted components -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
