#!/usr/bin/env python3
"""3D result figures (run from the project folder, inside IIC-OSIC-TOOLS):
  docs/ron_3d.png         transmission-gate on-resistance vs. input voltage at four PVT points (build/char/ron*)
  docs/spectrum_3d.png    8-bit output spectrum at every tested input frequency (build/8bit/studies/coverage/fin_*)
"""
import json, re, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

INK, GRID = "#1d2330", "#d7dbe0"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]          # categorical slots 1-4 (validated palette)


def style3d(ax):
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.pane.set_facecolor("#f7f8fa"); a.pane.set_edgecolor(GRID)
        a._axinfo["grid"].update(color=GRID, linewidth=0.6)
    ax.tick_params(labelsize=9.5, colors=INK)


def small(png):
    from PIL import Image
    Image.open(png).convert("RGB").quantize(colors=192, dither=Image.Dither.NONE).save(png, optimize=True)


# ------------------------------------------------------------------ transmission-gate R_on
def ron_3d():
    conds = [("ron", "tt, 27 °C, 1.80 V"), ("ron_tt_27C_0.9", "tt, 27 °C, 1.62 V"),
             ("ron_ss_125C_1", "ss, 125 °C, 1.80 V"), ("ron_ss_-40C_1", "ss, −40 °C, 1.80 V")]
    data = []
    for d, lab in conds:
        a = np.loadtxt(f"build/char/{d}/ron.txt", skiprows=1)
        vdd = float(re.search(r"Vdd vdd 0 ([0-9.]+)", Path(f"build/char/{d}/tb.cir").read_text()).group(1))
        v = a[:, 0]
        # R_on * W of the TG (NMOS W = 1 um, PMOS 2 um) from the 5 mV test voltage, in kOhm*um
        data.append((lab, vdd, v, 5e-3 / np.abs(a[:, 1]) / 1e3, 5e-3 / np.abs(a[:, 2]) / 1e3))
    zmin, zmax = -0.5, np.log10(max(max(r[3].max(), r[4].max()) for r in data)) + 0.2
    fig = plt.figure(figsize=(13, 6.6))
    for k, (col, flav) in enumerate(((3, "standard-Vt switch"), (4, "low-Vt (LVT) switch: the sized design"))):
        ax = fig.add_axes([0.0 + k * 0.49, 0.02, 0.50, 0.78], projection="3d")
        for i, row in enumerate(data):
            lab, vdd, v, z = row[0], row[1], row[2], np.log10(row[col])
            verts = [list(zip(v, np.full_like(v, i), z)) + [(v[-1], i, zmin), (v[0], i, zmin)]]
            ax.add_collection3d(Poly3DCollection(verts, facecolor=CAT[i], edgecolor=CAT[i], alpha=0.35, linewidths=1.6))
            jc = np.argmin(np.abs(v - vdd / 2))                 # Vcm = vdd/2: where the top-plate switch sits
            ax.plot([v[jc]], [i], [z[jc]], "o", color=INK, ms=5, zorder=10)
            ax.text(v[jc], i, z[jc] + 0.18, f"{row[col][jc]:.0f}", fontsize=9.5, color=INK, ha="center", zorder=11)
        ax.set_xlim(0, 1.8); ax.set_ylim(-0.5, len(data) - 0.5); ax.set_zlim(zmin, zmax)
        ax.set_yticks(range(len(data))); ax.set_yticklabels([r[0] for r in data], fontsize=9)
        zt = [0, 1, 2, 3]
        ax.set_zticks([t for t in zt if t <= zmax]); ax.set_zticklabels([f"{10 ** t:g}" for t in zt if t <= zmax])
        ax.set_xlabel("input voltage [V]", labelpad=6); ax.set_zlabel("R_on · W [kΩ·µm], log", labelpad=4)
        ax.view_init(elev=22, azim=-60); style3d(ax)
        ax.set_title(flav, fontsize=12.5, fontweight="bold", color=INK, pad=0)
    fig.text(0.03, 0.95, "Why the top-plate switch is hard: a transmission gate is weakest at mid-rail, where Vcm sits",
             fontsize=14.5, fontweight="bold", color=INK)
    fig.text(0.03, 0.905, "On-resistance of a 1 µm / 2 µm transmission gate across its input range (ngspice, SKY130 models). "
             "Dots and numbers: the value at Vcm = VDD/2.\nStandard-Vt devices barely conduct there at ss / −40 °C, so the "
             "generator picks LVT, which leaks instead when hot (section 12).", fontsize=10.5, color="#4b5563", va="top")
    fig.savefig("docs/ron_3d.png", dpi=100, facecolor="white"); plt.close(fig)
    small("docs/ron_3d.png")


# ------------------------------------------------------------------ 8-bit spectrum vs. input frequency
def spectrum_3d(bits=8, fft_n=128):
    from sargen import SarSpec, metrics
    from sargen.flow import _codes_from_wave
    from sargen.netlist import Timing
    from sargen.spice import read_wrdata
    spec = SarSpec(bits=bits); tim = Timing(bits, spec.tclk)
    rows = json.loads(Path(f"build/{bits}bit/studies/coverage/rows.json").read_text())
    runs = []
    for d in sorted(Path(f"build/{bits}bit/studies/coverage").glob("fin_*"), key=lambda p: int(p.name[4:])):
        cyc = int(d.name[4:]); codes = []
        for ch in sorted(d.glob("chunk_*")):
            n = 32 if len(codes) + 32 <= fft_n else fft_n - len(codes)
            codes += list(_codes_from_wave(read_wrdata(ch / "wave.txt"), tim, n, bits, spec.vdd))
        x = np.asarray(codes[:fft_n], float); x -= x.mean()
        p = np.abs(np.fft.rfft(x)) ** 2
        db = 10 * np.log10(p / p[cyc] + 1e-15)                  # dB relative to the input tone (dBc)
        r = rows[f"fin {cyc / fft_n:.3f} fs"]
        runs.append((cyc, np.arange(len(p)) / fft_n, db, r))
    floor = -90
    fig = plt.figure(figsize=(12, 7.4))
    ax = fig.add_axes([0.0, 0.0, 0.80, 0.84], projection="3d")
    shade = matplotlib.colors.LinearSegmentedColormap.from_list("s", ["#9cc3ee", "#123f78"])
    for i, (cyc, f, db, r) in enumerate(runs):
        y = cyc / fft_n
        z = np.maximum(db[1:], floor); fx = f[1:]
        verts = [list(zip(fx, np.full_like(fx, y), z)) + [(fx[-1], y, floor), (fx[0], y, floor)]]
        c = shade(i / max(1, len(runs) - 1))
        ax.add_collection3d(Poly3DCollection(verts, facecolor=c, edgecolor=c, alpha=0.28, linewidths=1.3))
    ax.set_xlim(0, 0.5); ax.set_ylim(0, 0.5); ax.set_zlim(floor, 5)
    ax.set_xlabel("output frequency [× fs]", labelpad=8); ax.set_ylabel("input frequency [× fs]", labelpad=8)
    ax.set_zlabel("power [dBc]", labelpad=4); ax.view_init(elev=24, azim=-62); style3d(ax)
    tab = ["input       ENOB   SFDR"] + [f"{c / fft_n:.3f} fs   {r['enob']:.2f}   {r['sfdr_db']:.0f} dB" for c, _, _, r in runs]
    fig.text(0.80, 0.62, "\n".join(tab), fontsize=10.5, family="monospace", color=INK, va="top",
             bbox=dict(boxstyle="round,pad=0.5", fc="#f7f8fa", ec=GRID))
    fig.text(0.03, 0.95, f"{bits}-bit converter: the spectrum stays clean up to the Nyquist frequency",
             fontsize=15, fontweight="bold", color=INK)
    fig.text(0.03, 0.905, f"Output spectrum ({fft_n}-point FFT, coherent tones) at each tested input frequency, schematic at "
             f"{spec.fs / 1e6:g} MS/s. The tall line is the input tone;\nno harmonic rises as the input approaches fs/2 "
             f"(SFDR {min(r[3]['sfdr_db'] for r in runs):.0f}–{max(r[3]['sfdr_db'] for r in runs):.0f} dB).",
             fontsize=10.5, color="#4b5563", va="top")
    fig.savefig("docs/spectrum_3d.png", dpi=100, facecolor="white"); plt.close(fig)
    small("docs/spectrum_3d.png")


if __name__ == "__main__":
    for f in sys.argv[1:] or ["ron_3d", "spectrum_3d"]:
        globals()[f](); print("done", f)
