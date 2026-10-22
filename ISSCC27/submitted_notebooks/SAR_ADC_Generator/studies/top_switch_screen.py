#!/usr/bin/env python3
"""Top-plate switch screen: which transmission-gate flavour (sargen.pdk.TG_FLAVORS) both holds the floating top plate
when hot and settles it when cold?  For the sized switch of one resolution, at each corner:
  hold  - switch off, top plate (C_total of the CDAC) started at Vcm +- 0.45 V and near either rail
          (the top plate swings over Vcm +- Vref/2 during a conversion): its leakage
          drift (after the first 10 %, which is charge sharing with the switch itself) scaled to one conversion, in LSB.  This leakage is what breaks the 8-bit core at 125 C.
  track - switch on: R_on at Vcm from a 1 mV DC test, and the number of time constants R_on * C_total that fit in the
          3/4 of the tracking phase the sizing gives the top switch; settling to 1/4 LSB needs ln(2^N / 0.25).
Writes results/<N>bit/sweeps/top_switch_screen.md.  Run inside IIC-OSIC-TOOLS:  python3 studies/top_switch_screen.py 8
"""
import dataclasses, json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sargen import SarSpec, spice
from sargen.netlist import tg_lines
from sargen.pdk import NFET_LVT, lib_line, mos

FLAVOURS = {"lvt": "LVT N + LVT P (sized)", "std": "SVT N + SVT P", "mix": "SVT N + LVT P", "mixp": "LVT N + SVT P",
            "n1": "LVT NMOS only, W_n", "n2": "LVT NMOS only, 2 W_n"}


def switch(fl, sw, a, b):
    """the top-plate switch between a and b: a transmission gate, or an LVT NMOS alone (n1, n2: width x1, x2)"""
    if fl in ("n1", "n2"):
        return [mos("Mtn", a, "phit", b, "0", NFET_LVT, sw["top_wn"] * int(fl[1]), 0.15)]
    return tg_lines("Mt", a, b, "phit", "phitb", sw["top_wn"], sw["top_wp"], fl)
CORNERS = [("tt", 27, 1.0), ("ff", 125, 1.0), ("fs", 125, 1.0), ("sf", -40, 1.0), ("ss", -40, 1.0), ("ss", -40, 0.9)]


def hold_net(sp, sw, fl, c_top, v0, t_end):
    return "\n".join([f"* top-plate hold, {fl}", lib_line(sp.corner), f".temp {sp.temp}", f"Vdd vdd 0 {sp.vdd}",
                      f"Vcm vcm 0 {sp.vcm}", "Vphit phit 0 0", f"Vphitb phitb 0 {sp.vdd}",
                      *switch(fl, sw, "top", "vcm"),
                      f"Ctop top 0 {c_top:.6g}", f".ic v(top)={v0:.6g}", f".tran {t_end / 400:.4g} {t_end:.6g} uic",
                      ".control", "set wr_singlescale", "set wr_vecnames", "run", "wrdata wave.txt v(top)", "quit",
                      ".endc", ".end"])


def track_net(sp, sw, fl):
    return "\n".join([f"* top-plate switch on-resistance, {fl}", lib_line(sp.corner), f".temp {sp.temp}",
                      f"Vdd vdd 0 {sp.vdd}", f"Vcm vcm 0 {sp.vcm}", f"Vt top vcm 1e-3", f"Vphit phit 0 {sp.vdd}",
                      "Vphitb phitb 0 0", *switch(fl, sw, "topx", "vcm"),
                      "Vm top topx 0", ".control", "op", "print i(Vm) > ron.txt", "quit", ".endc", ".end"])


def main(bits=8):
    base = Path(f"build/{bits}bit"); d = json.loads((base / "design.json").read_text())
    sw, c_top = d["sw"], d["cu"]["c_total"]
    out = base / "studies" / "top_switch_screen"
    rows, jobs, keys = [], [], []
    for fl in FLAVOURS:
        for c, t, s in CORNERS:
            b = SarSpec(bits=bits)
            sp = dataclasses.replace(b, corner=c, temp=float(t), vdd=b.vdd * s, vref=b.vref * s)
            t_conv = (bits + 1) * sp.tclk
            tag = f"{fl}_{c}_{t:+d}_{s:g}"
            for v0, name in ((sp.vcm + 0.45, "hp"), (sp.vcm - 0.45, "hn"), (sp.vdd - 0.02, "hP"), (0.02, "hN")):
                keys.append((fl, c, t, s, name)); jobs.append(dict(netlist=hold_net(sp, sw, fl, c_top, v0, t_conv),
                                                                  workdir=out / f"{tag}_{name}"))
            keys.append((fl, c, t, s, "track")); jobs.append(dict(netlist=track_net(sp, sw, fl), workdir=out / f"{tag}_on"))
    res = {}
    for k, wd in zip(keys, spice.run_many(jobs)):
        if k[-1] == "track":
            i = float(next(l for l in (Path(wd) / "ron.txt").read_text().splitlines() if "=" in l).split("=")[1])
            res.setdefault(k[:4], {})["ron"] = 1e-3 / abs(i)
        else:
            w = spice.read_wrdata(Path(wd) / "wave.txt")
            # leakage = the slow drift after the initial charge sharing with the switch's own capacitances (first 10 %),
            # scaled to the whole conversion
            t = w["time"]; v10 = np.interp(0.1 * t[-1], t, w["top"])
            res.setdefault(k[:4], {}).setdefault("drift", []).append(abs(w["top"][-1] - v10) / 0.9)
    need = math.log(2**bits / 0.25)
    md = [f"| top-plate switch | corner | R_on at Vcm [Ohm] | time constants in the tracking window (need {need:.1f}) "
          "| droop over one conversion [LSB] | verdict |", "|---|---|---|---|---|---|"]
    for (fl, c, t, s), r in res.items():
        sp = SarSpec(bits=bits)
        n_tau = 0.75 * d["timing"]["t_track"] / (r["ron"] * c_top)
        droop = max(r["drift"]) / (sp.lsb * s)
        ok = bool(n_tau >= need and droop < 0.25)
        r.update(n_tau=n_tau, droop_lsb=droop, ok=ok)
        md.append(f"| {FLAVOURS[fl]} | {c} {t:+d}C {1.8 * s:.2f}V | {r['ron']:.0f} | {n_tau:.1f} | {droop:.3f} | "
                  f"{'ok' if ok else ('leaks' if droop >= 0.25 else 'too slow')} |")
    md.append(f"\nSized switch W_n / W_p = {sw['top_wn']} / {sw['top_wp']} um, C_total = {c_top * 1e12:.2f} pF; "
              "droop limit 1/4 LSB; time constants from 3/4 of the tracking phase.")
    dst = Path(f"results/{bits}bit/sweeps/top_switch_screen.md"); dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(md) + "\n")
    (out / "screen.json").write_text(json.dumps({"|".join(map(str, k)): v for k, v in res.items()}, indent=1, default=float))
    print(dst.read_text())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
