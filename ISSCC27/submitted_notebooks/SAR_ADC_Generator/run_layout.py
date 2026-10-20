#!/usr/bin/env python3
"""Layout stage: generate blocks with gLayout and verify them (DRC, LVS, PNG).

Run with the gLayout environment:  python run_layout.py cdac --bits 4
(sizes come from build/<N>bit/design.json written by run_flow.py)
"""

import argparse
import json
import time
from pathlib import Path

from sargen.layout import verify


def do_cdac(bits, out):
    from sargen.layout import cdac
    design = json.loads(Path(f"build/{bits}bit/design.json").read_text())
    side = design["cu"]["side"]
    t0 = time.time()
    comp, info = cdac.build_cdac(bits, side, name=f"cdac{bits}b")
    gds = out / f"{comp.name}.gds"
    comp.write_gds(gds)
    info["gen_s"] = time.time() - t0
    ref = out / f"{comp.name}_ref.spice"
    ref.write_text(cdac.reference_netlist(bits, side, cell=comp.name))
    print(f"generated {gds} in {info['gen_s']:.1f} s: {info['rows']}x{info['cols']} units, "
          f"{info['width']:.1f} x {info['height']:.1f} um")
    for row in info["grid"]:
        print("   ", " ".join(f"{g:>2}" for g in row))
    return gds, ref, comp.name, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("block", choices=["cdac"])
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args()
    out = Path(f"build/{a.bits}bit/layout")
    out.mkdir(parents=True, exist_ok=True)
    gds, ref, cell, info = do_cdac(a.bits, out)
    if not a.no_verify:
        t = time.time()
        info["drc_klayout"] = verify.drc_klayout(gds, out / "drc")
        info["drc_magic"] = verify.drc_magic(gds, cell, out / "drc")
        info["lvs"] = verify.lvs(gds, cell, ref, cell, out / "lvs")
        verify.render_png(gds, out / f"{cell}.png")
        print(f"DRC klayout {info['drc_klayout']['total']} {info['drc_klayout']['rules']}")
        print(f"DRC magic   {info['drc_magic']['total']} {info['drc_magic']['rules']}")
        print(f"LVS {'MATCH' if info['lvs']['match'] else 'FAIL'} devices {info['lvs']['devices']} "
              f"{info['lvs']['summary']}  ({time.time() - t:.0f} s)")
    (out / f"{cell}.json").write_text(json.dumps(info, indent=1, default=str))


if __name__ == "__main__":
    main()
