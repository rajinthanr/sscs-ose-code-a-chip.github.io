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
    ap.add_argument("--only", nargs="*", help="subset of case names to run (merged into prepost.json)")
    a = ap.parse_args()
    base = Path(f"build/{a.bits}bit")
    design = json.loads((base / "design.json").read_text())
    spec = SarSpec(bits=a.bits)
    pex_dir = base / "layout" / "pex"
    cdac = dict(cdac_lines=nl.load_cdac_extraction(pex_dir / f"cdac{a.bits}b_pex.spice", a.bits))
    cmp_ = dict(cmp_subckt=nl.load_strongarm_extraction(pex_dir / "strongarm_pex.spice"))
    sw = dict(sw_subckt=nl.wrap_extraction(pex_dir / "switches_pex.spice", "switches", nl.switch_pins(a.bits)))
    lay = base / "layout"
    cdacsw = {}
    if (pex_dir / f"cdacsw{a.bits}b_pex.spice").exists():
        pins = nl.subckt_pins(lay / f"cdacsw{a.bits}b_ref.spice", f"cdacsw{a.bits}b")
        cdacsw = dict(cdacsw=(nl.wrap_extraction(pex_dir / f"cdacsw{a.bits}b_pex.spice", "cdacsw", pins), pins))
    cases = [("schematic", {}), ("extracted CDAC", cdac), ("extracted comparator", cmp_),
             ("compact CDAC+switches", cdacsw), ("compact CDAC+switches + comparator", {**cdacsw, **cmp_}),
             ("extracted switches", sw), ("all blocks extracted", {**cdac, **cmp_, **sw})]
    if a.only:
        cases = [c for c in cases if c[0] in a.only]
    out = base / "postlayout"
    rows = json.loads((out / "prepost.json").read_text()) if a.only and (out / "prepost.json").exists() else {}
    for name, kw in cases:
        r = evaluate(spec, design, out / name.replace(" ", "_"), hits=a.hits, fft_n=a.fft_n, **kw)
        rows[name] = r
        print(f"{name:28s} ENOB {r['enob']:.3f}  DNL {r['dnl_t']:.3f}  INL {r['inl_t']:.3f}  offset {r['offset_lsb']:+.3f}  "
              f"gain {r['gain_lsb']:+.3f} LSB  {r['p_uw']:.2f} uW", flush=True)
        (out / "prepost.json").write_text(json.dumps(rows, indent=1, default=float))
    md = ["| metric | " + " | ".join(rows) + " |", "|---|" + "---|" * len(rows)]
    for k, lbl in (("enob", "ENOB [bit]"), ("dnl_t", "max DNL [LSB]"), ("inl_t", "max INL [LSB]"),
                   ("offset_lsb", "offset [LSB]"), ("gain_lsb", "gain error [LSB]"), ("p_uw", "power [uW]")):
        md.append(f"| {lbl} | " + " | ".join(f"{r[k]:.3f}" for r in rows.values()) + " |")
    (out / "prepost.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
