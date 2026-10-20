#!/usr/bin/env python3
"""Pre- vs post-layout comparison: the same transistor-level tests with layout-extracted blocks.

python3 run_postlayout.py --bits 4      (needs build/<N>bit/design.json and the layout extraction)
"""

import argparse
import json
from pathlib import Path

from sargen import SarSpec
from sargen import netlist as nl
from sargen.sweep import evaluate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--hits", type=int, default=32)
    ap.add_argument("--fft-n", type=int, default=128)
    a = ap.parse_args()
    base = Path(f"build/{a.bits}bit")
    design = json.loads((base / "design.json").read_text())
    spec = SarSpec(bits=a.bits)
    pex = base / "layout" / "pex" / f"cdac{a.bits}b_pex.spice"
    out = base / "postlayout"
    rows = {}
    for name, kw in (("schematic", {}), ("extracted CDAC", dict(cdac_lines=nl.load_cdac_extraction(pex, a.bits)))):
        r = evaluate(spec, design, out / name.replace(" ", "_"), hits=a.hits, fft_n=a.fft_n, **kw)
        rows[name] = r
        print(f"{name:15s} ENOB {r['enob']:.3f}  DNL {r['dnl_t']:.3f}  INL {r['inl_t']:.3f}  offset {r['offset_lsb']:+.3f}  "
              f"gain {r['gain_lsb']:+.3f} LSB  {r['p_uw']:.2f} uW", flush=True)
    (out / "prepost.json").write_text(json.dumps(rows, indent=1, default=float))
    md = ["| metric | schematic | extracted CDAC |", "|---|---|---|"]
    for k, lbl in (("enob", "ENOB [bit]"), ("dnl_t", "max DNL [LSB]"), ("inl_t", "max INL [LSB]"),
                   ("offset_lsb", "offset [LSB]"), ("gain_lsb", "gain error [LSB]"), ("p_uw", "power [uW]")):
        md.append(f"| {lbl} | {rows['schematic'][k]:.3f} | {rows['extracted CDAC'][k]:.3f} |")
    (out / "prepost.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
