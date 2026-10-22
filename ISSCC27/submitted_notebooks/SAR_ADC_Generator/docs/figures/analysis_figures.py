#!/usr/bin/env python3
"""Explanatory figures from SARGen's own rules, model and results (run from the project folder):
  docs/sizing_space_3d.png   unit-capacitor side vs. resolution and DNL target (sizing.py rules)
  docs/yield.png             DNL yield vs. unit-capacitor side, per resolution (PDK-calibrated behavioral model)
  docs/staircase_3d.png      the binary search of every input, 4 bit (ideal converter)
  docs/pvt_heatmap.png       max DNL over corner x temperature, schematic vs. extracted core (4 bit)
"""
import json, math, re, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sargen import SarSpec
from sargen.model import SarModel
from sargen.pdk import MIM_MIN_SIDE

INK, MUTED, GRID = "#1d2330", "#6b7280", "#d7dbe0"
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b9bdc5"
BLUES = LinearSegmentedColormap.from_list("b", ["#e8f1fb", "#9cc3ee", "#2a78d6", "#123f78"])
CHAR = json.loads(Path("results/8bit/summary.json").read_text())["char"]
A_C = CHAR["mim_match_pct_um"] / 100                  # sigma(dC/C) * sqrt(area), um
CA, CP = CHAR["mim_ca_fF_um2"] * 1e-15, CHAR["mim_cp_fF_um"] * 1e-15


def titles(fig, title, sub):
    fig.text(0.03, 0.955, title, fontsize=15, fontweight="bold", color=INK)
    fig.text(0.03, 0.915, sub, fontsize=11, color="#4b5563", va="top")


def style3d(ax):
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.pane.set_facecolor("#f7f8fa"); a.pane.set_edgecolor(GRID)
        a._axinfo["grid"].update(color=GRID, linewidth=0.6)
    ax.tick_params(labelsize=9.5, colors=INK)


# ------------------------------------------------------------------ 1. sizing design space
def side_rule(bits, dnl3):
    """sizing.py: side = max(matching, kT/C, PDK minimum); returns (side_um, limiter)."""
    spec = SarSpec(bits=8)                               # vref, temperature, noise target
    sig_u = dnl3 / (3 * math.sqrt(2**bits - 1))
    s_match = A_C / sig_u
    lsb = spec.vref / 2**bits
    c_ktc = 1.380649e-23 * (spec.temp + 273.15) / (spec.noise_lsb * lsb) ** 2
    s_ktc = (-4 * CP + math.sqrt(16 * CP**2 + 4 * CA * c_ktc / 2**bits)) / (2 * CA)
    lim = max([("matching", s_match), ("kT/C", s_ktc), ("min", MIM_MIN_SIDE)], key=lambda t: t[1])
    return lim[1], lim[0]


def sizing_space():
    B = np.linspace(4, 8, 81); D = np.linspace(0.25, 1.0, 61)
    BB, DD = np.meshgrid(B, D)
    S = np.vectorize(lambda b, d: side_rule(b, d)[0])(BB, DD)
    L = np.vectorize(lambda b, d: side_rule(b, d)[1])(BB, DD)
    col = np.empty(S.shape + (4,))
    col[L == "min"] = matplotlib.colors.to_rgba(GREY, 0.85)
    col[L == "matching"] = matplotlib.colors.to_rgba(BLUE, 0.80)
    col[L == "kT/C"] = matplotlib.colors.to_rgba(ORANGE, 0.85)
    fig = plt.figure(figsize=(11, 7.6))
    ax = fig.add_axes([0.02, 0.02, 0.76, 0.84], projection="3d")
    ax.plot_surface(BB, DD, S, facecolors=col, rstride=2, cstride=2, linewidth=0.15, edgecolor="white", shade=False)
    for b in (4, 6, 8):
        s = json.loads(Path(f"results/{b}bit/summary.json").read_text())["design"]["cu"]["side"]
        ax.plot([b, b], [0.5, 0.5], [s, s + 0.45], color=INK, lw=1.2, zorder=10)
        ax.scatter([b], [0.5], [s + 0.05], s=60, color=INK, depthshade=False, zorder=10)
        ax.text(b, 0.5, s + 0.6, f"{b} bit: {s:.1f} µm", fontsize=10.5, color=INK, ha="center", zorder=11)
    ax.set_xlabel("resolution [bits]", labelpad=8); ax.set_ylabel("DNL target, 3σ [LSB]", labelpad=8)
    ax.set_zlabel("unit-capacitor side [µm]", labelpad=6)
    ax.set_zlim(0, np.ceil(S.max())); ax.view_init(elev=24, azim=-128); style3d(ax)
    any_ktc = (L == "kT/C").any()
    fig.legend(handles=[Patch(color=GREY, label="PDK minimum (2 µm) sets it"),
                        Patch(color=BLUE, label="capacitor matching sets it")] +
               ([Patch(color=ORANGE, label="kT/C noise sets it")] if any_ktc else []),
               loc="upper right", bbox_to_anchor=(0.97, 0.80), frameon=False, fontsize=11)
    titles(fig, "How SARGen picks the unit capacitor",
           "Each point is the sizing rule's answer over the generator's range. With loose DNL targets the PDK's minimum"
           "\nMIM capacitor is accurate enough; with more bits or a tighter target, matching (2.8 %·µm, PDK model) grows it."
           "\nDots: the three sized designs, at a DNL target of 0.5 LSB."
           + ("" if any_ktc else "\nkT/C noise never sets the size at 4 to 8 bits."))
    fig.savefig("docs/sizing_space_3d.png", dpi=100, facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------ 2. yield surface
def dnl_max(model):
    k = np.arange(1, 2**model.bits)
    ctrl = (k[:, None] >> np.arange(model.bits)) & 1
    t = ctrl @ model.caps / model.c_sum                   # transition levels / Vref (truncating SAR)
    return np.abs(np.diff(t) * 2**model.bits - 1).max()


def yield_surface(runs=400):
    """2D on purpose: the surface is flat at 100 % except for 7-8 bits with small capacitors."""
    sides = np.linspace(1.0, 3.5, 26); bits = [4, 5, 6, 7, 8]
    shade = LinearSegmentedColormap.from_list("s", ["#9cc3ee", "#123f78"])
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=0.86, top=0.78, bottom=0.11)
    for k, b in enumerate(bits):
        y = [np.mean([dnl_max(SarModel(b, cu_sigma=A_C / s, seed=r)) < 0.5 for r in range(runs)]) * 100 for s in sides]
        ax.plot(sides, y, color=shade(k / 4), lw=2, label=f"{b} bit")
    pts = {}
    for b in (4, 6, 8):
        s = json.loads(Path(f"results/{b}bit/summary.json").read_text())["design"]["cu"]["side"]
        pts[b] = (s, np.mean([dnl_max(SarModel(b, cu_sigma=A_C / s, seed=r)) < 0.5 for r in range(runs)]) * 100)
        ax.plot([s], [pts[b][1]], "o", ms=8, color=ORANGE, mec="white", mew=1.5, zorder=5)
    (s4, y4), (s6, y6), (s8, y8) = pts[4], pts[6], pts[8]
    lab46 = (f"4- and 6-bit designs: {s4:.1f} µm, {min(y4, y6):.0f} %" if s4 == s6 else f"4-bit: {s4:.1f} µm, {y4:.0f} %")
    ax.annotate(lab46, (s4, min(y4, y6)), xytext=(s4 + 0.12, 74), fontsize=10.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.annotate(f"8-bit design: {s8:.1f} µm, {y8:.0f} %", (s8, y8), xytext=(s8 + 0.1, 60), fontsize=10.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.legend(title="resolution", loc="lower right", frameon=False, fontsize=10.5, title_fontsize=10.5)
    ax.axvline(MIM_MIN_SIDE, color=MUTED, lw=1, ls="--")
    ax.text(MIM_MIN_SIDE - 0.04, 22, "PDK minimum\nused by SARGen", ha="right", fontsize=10, color=MUTED)
    ax.set_xlabel("unit-capacitor side [µm]"); ax.set_ylabel("chips with |DNL| < 0.5 LSB [%]")
    ax.set_ylim(0, 102); ax.set_xlim(1.0, 3.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.6)
    fig.text(0.03, 0.94, "Yield: how many chips meet DNL < 0.5 LSB", fontsize=15, fontweight="bold", color=INK)
    fig.text(0.03, 0.885, f"{runs} random chips per point: capacitor mismatch from the PDK model in the behavioral SAR. Up to 6 bits"
             "\nthe minimum capacitor already gives ~100 %; at 8 bits the sized 2.7 µm capacitor is what keeps the yield high.",
             fontsize=10.5, color="#4b5563", va="top")
    fig.savefig("docs/yield.png", dpi=100, facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------ 3. binary-search staircase
def staircase(bits=4, n=16):
    m = SarModel(bits); vref = m.vref
    vins = (np.arange(n) + 0.5) / n * vref
    fig = plt.figure(figsize=(11, 7.6))
    ax = fig.add_axes([0.02, 0.02, 0.78, 0.84], projection="3d")
    cmap = LinearSegmentedColormap.from_list("v", ["#9cc3ee", "#2a78d6", "#123f78"])
    for j, v in enumerate(vins):
        tr = m.trace(v)
        z = [s["vdac"] for s in tr if s["phase"] == "trial"] + [tr[-1]["vdac"]]
        x = np.arange(1, len(z) + 1)
        xs = np.repeat(x, 2)[1:]; zs = np.repeat(z, 2)[:-1]     # steps, not ramps
        ax.plot(xs, np.full_like(xs, v, dtype=float), zs, color=cmap(j / n), lw=2.0, alpha=0.95)
    # the target: the output level equals the input
    X, V = np.meshgrid([1, bits + 1], [0, vref])
    ax.plot_surface(X, V, V, color="#f2b48f", alpha=0.18, linewidth=0)
    ax.set_xticks(range(1, bits + 2)); ax.set_xticklabels([f"bit {bits - 1 - i}" for i in range(bits)] + ["code"])
    ax.set_xlabel("conversion step", labelpad=10); ax.set_ylabel("input voltage [V]", labelpad=8)
    ax.set_zlabel("DAC level tried [V]", labelpad=6); ax.view_init(elev=18, azim=-58); style3d(ax)
    titles(fig, "Every input walks the same binary staircase",
           f"One input per code ({n}), {bits}-bit SAR. Each line is one conversion: start at half scale, then move up or down by half as much"
           "\nat every step. Every line ends within one LSB below the orange plane (DAC level = input): that last level is the code.")
    fig.savefig("docs/staircase_3d.png", dpi=100, facecolor="white"); plt.close(fig)


# ------------------------------------------------------------------ 4. PVT heatmap (2D on purpose)
def pvt_heatmap():
    def grid_from(md):
        rows = [ln for ln in Path(md).read_text().splitlines() if ln.startswith("|") and re.match(r"\| \w\w [+-]", ln)]
        hdr = [h.strip() for h in Path(md).read_text().splitlines()[0].strip("|").split("|")]
        g = {}
        for ln in rows:
            c = dict(zip(hdr, [x.strip() for x in ln.strip("|").split("|")]))
            if abs(float(c["vdd"]) - 1.8) < 1e-6:
                g[(c["corner"], int(float(c["temp"])))] = float(c["dnl_t"])
        return g
    corners, temps = ["tt", "ss", "ff", "sf", "fs"], [-40, 27, 125]
    data = [("schematic", grid_from("results/4bit/sweeps/pvt_4b.md")),
            ("extracted core (layout)", grid_from("results/4bit/layout/pvt_core.md"))]
    vmax = max(max(g.values()) for _, g in data)
    fig, axs = plt.subplots(1, 2, figsize=(11, 5.0))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.66, bottom=0.11, wspace=0.18)
    for ax, (name, g) in zip(axs, data):
        M = np.array([[g[(c, t)] for t in temps] for c in corners])
        ax.imshow(M, cmap=BLUES, vmin=0, vmax=vmax, aspect="auto")
        for i in range(len(corners)):
            for j in range(len(temps)):
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=11,
                        color="white" if M[i, j] > 0.55 * vmax else INK)
        ax.set_xticks(range(3)); ax.set_xticklabels([f"{t} °C" for t in temps])
        ax.set_yticks(range(5)); ax.set_yticklabels(corners); ax.set_title(name, fontsize=12, loc="left", color=INK)
        ax.tick_params(length=0, labelsize=10.5)
        for s in ax.spines.values():
            s.set_visible(False)
    fig.text(0.03, 0.93, "4-bit converter across process corners and temperature: max |DNL| [LSB]", fontsize=14.5,
             fontweight="bold", color=INK)
    fig.text(0.03, 0.85, "Every point stays far below 0.5 LSB. The darkest cells are the hot fs / ff corners, where the "
             "top-plate switch leaks;\nthe effect is smaller in the extracted layout (likely its extra top-plate wiring capacitance; not separately tested).\nResolved to 1/16 LSB (16 ramp points per code): 0.00 means below that step.",
             fontsize=10.5, color="#4b5563", va="top")
    fig.savefig("docs/pvt_heatmap.png", dpi=100, facecolor="white"); plt.close(fig)


def small(png):
    """flat-colour figures fit a palette: ~3x smaller PNGs in the notebook"""
    from PIL import Image
    Image.open(png).convert("RGB").quantize(colors=192, dither=Image.Dither.NONE).save(png, optimize=True)


if __name__ == "__main__":
    for f in sys.argv[1:] or ["sizing_space", "yield_surface", "staircase", "pvt_heatmap"]:
        globals()[f](); print("done", f)
    for png in ("sizing_space_3d", "yield", "staircase_3d", "pvt_heatmap"):
        small(f"docs/{png}.png")
