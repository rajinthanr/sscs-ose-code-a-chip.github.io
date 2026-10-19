"""PDK characterization with ngspice: every number the sizing step needs comes from here.

* Pelgrom coefficient A_VT of nfet/pfet (many mismatch instances in one netlist)
* on-resistance x width of the transmission gate and of the DAC drivers
* MIM capacitance per area and per perimeter
* MIM matching coefficient (read from the PDK model card)
* comparator offset distribution (after sizing; many comparator instances)
"""

import json
from pathlib import Path

import numpy as np

from . import netlist as nl
from .pdk import NFET, PFET, lib_line, mim, mim_matching_pct_um, mos
from .spice import read_print, read_wrdata, run, run_many

AVT_GEOMS = [(2.0, 0.5), (4.0, 1.0)]   # (W, L) in um
N_MC = 200                              # instances per geometry


def _avt_netlist(corner, temp, vdd):
    lines = [f"* A_VT extraction", lib_line(corner, mismatch=True), f".temp {temp}",
             f"Vdd vdd 0 {vdd}"]
    for g, (w, l) in enumerate(AVT_GEOMS):
        i_bias = 1e-6 * w / l           # moderate inversion
        for k in range(N_MC):
            lines += [mos(f"N{g}_{k}", f"gn{g}_{k}", f"gn{g}_{k}", "0", "0", NFET, w, l),
                      f"In{g}_{k} vdd gn{g}_{k} {i_bias:.4g}",
                      mos(f"P{g}_{k}", f"gp{g}_{k}", f"gp{g}_{k}", "vdd", "vdd", PFET, w, l),
                      f"Ip{g}_{k} gp{g}_{k} 0 {i_bias:.4g}"]
    lines += [".control", "op", "print all > op.txt", "quit", ".endc", ".end"]
    return "\n".join(lines)


def _ron_netlist(corner, temp, vdd):
    """Small-signal on-resistance vs. signal level for W = 1 um devices."""
    L = 0.15
    return "\n".join([
        "* switch on-resistance", lib_line(corner), f".temp {temp}",
        f"Vdd vdd 0 {vdd}", "Vin a 0 0",
        # transmission gate Wn = 1, Wp = 2
        "Vt b a 0.005", mos("Tn", "a", "vdd", "b", "0", NFET, 1, L),
        mos("Tp", "a", "0", "b", "vdd", PFET, 2, L),
        # NMOS driver (gate = vdd) and PMOS driver (gate = 0), source tied to rail
        "Vn bn 0 0.005", mos("Dn", "bn", "vdd", "0", "0", NFET, 1, L),
        "Vp bp vdd -0.005", mos("Dp", "bp", "0", "vdd", "vdd", PFET, 1, L),
        ".control", f"dc Vin 0 {vdd} 0.01", "set wr_singlescale", "set wr_vecnames",
        "wrdata ron.txt i(Vt) i(Vn) i(Vp)", "quit", ".endc", ".end"])


def _mim_netlist(corner, temp):
    sides = [(5, 5), (20, 20), (5, 40)]
    lines = ["* MIM capacitance", lib_line(corner), f".temp {temp}"]
    for k, (w, l) in enumerate(sides):
        lines += [f"Vc{k} t{k} 0 DC 0 AC 1", mim(f"C{k}", f"t{k}", "0", w, l)]
    lines += [".control", "ac lin 1 1meg 1meg"]
    lines += [f"let c{k} = imag(-i(Vc{k}))/(2*pi*1e6)" for k in range(len(sides))]
    lines += ["print " + " ".join(f"c{k}" for k in range(len(sides))) + " > mim.txt",
              "quit", ".endc", ".end"]
    return "\n".join(lines), sides


def characterize_pdk(spec, workdir: Path, force=False) -> dict:
    """Run (or load cached) PDK characterization for this corner/temperature/supply."""
    workdir = Path(workdir)
    cache = workdir / f"pdk_char_{spec.corner}_{spec.temp:g}C_{spec.vdd:g}V.json"
    if cache.exists() and not force:
        return json.loads(cache.read_text())

    mim_txt, sides = _mim_netlist(spec.corner, spec.temp)
    d_avt, d_ron, d_mim = run_many([
        dict(netlist=_avt_netlist(spec.corner, spec.temp, spec.vdd), workdir=workdir / "avt", seed=1),
        dict(netlist=_ron_netlist(spec.corner, spec.temp, spec.vdd), workdir=workdir / "ron"),
        dict(netlist=mim_txt, workdir=workdir / "mim"),
    ])

    # --- A_VT: sigma(dVT) of a pair = sqrt(2) * sigma(single); A_VT = sigma(dVT) * sqrt(WL)
    op = read_print(d_avt / "op.txt")
    avt = {"nfet": [], "pfet": []}
    for g, (w, l) in enumerate(AVT_GEOMS):
        vn = np.array([op[f"gn{g}_{k}"] for k in range(N_MC)])
        vp = np.array([spec.vdd - op[f"gp{g}_{k}"] for k in range(N_MC)])
        avt["nfet"].append(np.sqrt(2) * vn.std(ddof=1) * np.sqrt(w * l) * 1e3)
        avt["pfet"].append(np.sqrt(2) * vp.std(ddof=1) * np.sqrt(w * l) * 1e3)

    # --- on-resistance (worst case over the signal range for the TG)
    r = read_wrdata(d_ron / "ron.txt")
    vin = r[list(r)[0]]
    r_tg = 0.005 / np.abs(r["i(vt)"])
    r_n = 0.005 / np.abs(r["i(vn)"][0])
    r_p = 0.005 / np.abs(r["i(vp)"][0])

    # --- MIM: C = ca*W*L + cp*2(W+L), least squares over the three geometries
    c = read_print(d_mim / "mim.txt")
    A = np.array([[w * l, 2 * (w + l)] for w, l in sides])
    y = np.array([c[f"c{k}"] for k in range(len(sides))])
    (ca, cperim), *_ = np.linalg.lstsq(A, y, rcond=None)

    res = dict(
        corner=spec.corner, temp=spec.temp, vdd=spec.vdd,
        avt_n_mVum=float(np.mean(avt["nfet"])), avt_p_mVum=float(np.mean(avt["pfet"])),
        avt_geoms=AVT_GEOMS, avt_n_each=avt["nfet"], avt_p_each=avt["pfet"],
        ron_tg_ohm_um=float(r_tg.max()), ron_tg_vin=vin.tolist(), ron_tg_curve=(r_tg).tolist(),
        ron_n_ohm_um=float(r_n), ron_p_ohm_um=float(r_p),
        mim_ca_fF_um2=float(ca * 1e15), mim_cp_fF_um=float(cperim * 1e15),
        mim_match_pct_um=mim_matching_pct_um(),
    )
    cache.write_text(json.dumps(res, indent=1))
    return res


def comparator_offset_mc(spec, design, workdir: Path, n_inst=24, n_jobs=8, vspan=None,
                         n_steps=120) -> dict:
    """Offset distribution of the sized comparator; returns offsets [V] for every instance."""
    tclk = 5e-9
    vspan = vspan or float(np.clip(6 * design["cmp"]["sigma_os_est"], 0.015, 0.2))
    jobs = [dict(netlist=nl.comparator_mc_testbench(spec, design, n_inst, vspan, n_steps, tclk),
                 workdir=Path(workdir) / f"cmp_mc_{j}", seed=100 + j) for j in range(n_jobs)]
    offsets = []
    slope = 2 * vspan / (n_steps * tclk)
    for d in run_many(jobs):
        w = read_wrdata(d / "wave.txt")
        t = w[list(w)[0]]
        t_dec = (np.arange(n_steps) + 0.9) * tclk          # read-out instants (clk still high)
        vin_dec = spec.vcm - vspan + slope * (t_dec - 0.4 * tclk)  # input at the rising clk edge
        for k in range(n_inst):
            q = np.interp(t_dec, t, w[f"qp{k}"]) > spec.vdd / 2  # high while inp < vcm
            flip = np.nonzero(~q)[0]
            if len(flip):
                offsets.append(vin_dec[flip[0]] - spec.vcm)
    offsets = np.array(offsets)
    return dict(offsets=offsets.tolist(), sigma=float(offsets.std(ddof=1)),
                mean=float(offsets.mean()), n=len(offsets), vspan=vspan)
