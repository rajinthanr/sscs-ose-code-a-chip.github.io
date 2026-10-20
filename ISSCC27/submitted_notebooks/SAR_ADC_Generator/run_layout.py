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


def do_comparator(bits, out):
    from sargen import SarSpec
    from sargen import netlist as nl
    from sargen.layout import cell
    design = json.loads(Path(f"build/{bits}bit/design.json").read_text())
    t0 = time.time()
    nrow, prow = cell.strongarm_devices(design["cmp"])
    comp, info = cell.build_cell("strongarm", nrow, prow, cell.STRONGARM_PINS)
    gds = out / "strongarm.gds"
    comp.write_gds(gds)
    info["gen_s"] = time.time() - t0
    ref = out / "strongarm_ref.spice"
    ref.write_text(nl.strongarm_subckt(design["cmp"]) + "\n")
    print(f"generated {gds} in {info['gen_s']:.1f} s: {info['width']:.1f} x {info['height']:.1f} um, "
          f"channels {info['channels']}")
    return gds, ref, "strongarm", info


def do_switches(bits, out):
    from sargen.layout import cell
    design = json.loads(Path(f"build/{bits}bit/design.json").read_text())
    t0 = time.time()
    nrow, prow, pins = cell.switch_devices(design, bits)
    comp, info = cell.build_cell("switches", nrow, prow, pins)
    gds = out / "switches.gds"
    comp.write_gds(gds)
    info["gen_s"] = time.time() - t0
    ref = out / "switches_ref.spice"
    ref.write_text(cell.reference_netlist("switches", nrow, prow, pins))
    print(f"generated {gds} in {info['gen_s']:.1f} s: {info['width']:.1f} x {info['height']:.1f} um")
    return gds, ref, "switches", info


def do_cdacsw(bits, out):
    from sargen.layout import tilearray
    design = json.loads(Path(f"build/{bits}bit/design.json").read_text())
    t0 = time.time()
    comp, info, ref_txt = tilearray.build_array(design, bits, name=f"cdacsw{bits}b")
    gds = out / f"{comp.name}.gds"
    comp.write_gds(gds)
    info["gen_s"] = time.time() - t0
    ref = out / f"{comp.name}_ref.spice"
    ref.write_text(ref_txt)
    print(f"generated {gds} in {info['gen_s']:.1f} s: tile {info['tile']} um, {info['ctrl_rails']} control rails, "
          f"block {info['width']:.1f} x {info['height']:.1f} um")
    return gds, ref, comp.name, info


TEST_RAILS = ["phis", "phisb", "phig", "phigb", "pg_0", "ng_0", "pg_1", "ng_1"]
TEST_GATES = [dict(en="phig", enb="phigb", pg="pg_0", ng="ng_0"), dict(en="phis", enb="phisb", pg="pg_1", ng="ng_1"),
              dict(en="phig", enb="phigb", pg="pg_1", ng="ng_1"), dict(en="phis", enb="phisb", pg="pg_0", ng="ng_0")]


def do_unit(bits, out, abut=False):
    from sargen.layout import unitcell
    design = json.loads(Path(f"build/{bits}bit/design.json").read_text())
    t0 = time.time()
    if abut:
        comp, plan, ref_txt = unitcell.build_abut_test(design, TEST_RAILS, TEST_GATES)
    else:
        comp, plan, ref_txt = unitcell.build_unit_cell(design, TEST_RAILS, TEST_GATES[0])
    gds = out / f"{comp.name}.gds"
    comp.write_gds(gds)
    ref = out / f"{comp.name}_ref.spice"
    ref.write_text(ref_txt)
    info = dict(cell_w=plan.W, cell_h=plan.H, gen_s=time.time() - t0)
    bb = comp.bbox
    info.update(width=float(bb[1][0] - bb[0][0]), height=float(bb[1][1] - bb[0][1]))
    print(f"generated {gds}: unit cell {plan.W:.2f} x {plan.H:.2f} um ({plan.W * plan.H:.1f} um^2), "
          f"block {info['width']:.2f} x {info['height']:.2f} um")
    return gds, ref, comp.name, info


def do_cdacu(bits, out):
    from sargen.layout import unitcell
    design = json.loads(Path(f"build/{bits}bit/design.json").read_text())
    t0 = time.time()
    comp, info, ref_txt = unitcell.build_unit_array(design, bits)
    gds = out / f"{comp.name}.gds"
    comp.write_gds(gds)
    info["gen_s"] = time.time() - t0
    ref = out / f"{comp.name}_ref.spice"
    ref.write_text(ref_txt)
    print(f"generated {gds} in {info['gen_s']:.1f} s: cell {info['cell'][0]:.2f} x {info['cell'][1]:.2f} um, "
          f"{info['ctrl_rails']} control rails, block {info['width']:.1f} x {info['height']:.1f} um")
    for row in info["grid"]:
        print("   ", " ".join(f"{g:>2}" for g in row))
    return gds, ref, comp.name, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("block", choices=["cdac", "comparator", "switches", "cdacsw", "unitcell", "unit2x2", "cdacu"])
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--no-verify", action="store_true")
    a = ap.parse_args()
    out = Path(f"build/{a.bits}bit/layout")
    out.mkdir(parents=True, exist_ok=True)
    gds, ref, cell, info = {"cdac": do_cdac, "comparator": do_comparator, "switches": do_switches,
                            "cdacsw": do_cdacsw, "unitcell": do_unit,
                            "unit2x2": lambda b, o: do_unit(b, o, abut=True), "cdacu": do_cdacu}[a.block](a.bits, out)
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
