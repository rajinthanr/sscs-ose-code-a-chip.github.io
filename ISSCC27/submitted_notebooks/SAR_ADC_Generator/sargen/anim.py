"""Animated explanation of one SAR conversion (binary search + CDAC switching)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle

from .model import SarModel

COLORS = {"vin": "#4C9BE8", "vref": "#E8744C", "gnd": "#8A8F98"}


def _frames(model: SarModel, vin: float):
    """Each trial is shown twice: 'try bit = 1' and then the comparator decision."""
    steps = model.trace(vin)
    frames = [dict(steps[0], stage="sample")]
    for s in steps[1:-1]:
        frames.append(dict(s, stage="try"))
        frames.append(dict(s, stage="decide"))
    frames.append(dict(steps[-1], stage="done"))
    return frames, steps[-1]["code"]


def _bit_symbol(f, i):
    """Text for bit i in a frame: decided value, '?' under test, '_' not yet tried."""
    if f["stage"] == "sample":
        return "_"
    if f["stage"] == "done" or i > f["bit"]:
        return str(int(f["ctrl"][i]))
    if i == f["bit"]:
        return "?" if f["stage"] == "try" else str(int(f["decision"]))
    return "_"


def animate_conversion(model: SarModel, vin: float, path=None, fps: float = 0.8):
    """Build the animation; save it as GIF when `path` is given. Returns the FuncAnimation."""
    n = model.bits
    frames, code = _frames(model, vin)
    lsb = model.vref / 2**n

    fig = plt.figure(figsize=(11, 5.6))
    gs = fig.add_gridspec(2, 2, height_ratios=[3, 1.25], width_ratios=[1.25, 1])
    ax_v = fig.add_subplot(gs[0, 0])
    ax_c = fig.add_subplot(gs[0, 1])
    ax_t = fig.add_subplot(gs[1, :])

    # capacitor bar widths proportional to capacitance (LSB first, then dummy)
    widths = list(model.caps) + [model.c_dummy]
    labels = [f"C{i}\n{2**i}C" for i in range(n)] + ["Cd\n1C"]
    order = list(range(n - 1, -1, -1)) + [n]          # draw MSB on the left
    total = sum(widths)

    def cap_conn(frame, j):
        if frame["stage"] == "sample":
            return "vin"
        if j == n:
            return "gnd"
        if frame["stage"] == "decide" and j == frame["bit"]:
            return "vref" if frame["decision"] else "gnd"
        return "vref" if frame["ctrl"][j] else "gnd"

    def draw(k):
        f = frames[k]
        for ax in (ax_v, ax_c, ax_t):
            ax.clear()

        # --- binary search staircase ---
        done = [fr for fr in frames[: k + 1] if fr["stage"] == "try"]
        ax_v.axhline(vin, color=COLORS["vin"], lw=2, label=f"Vin = {vin:.3f} V")
        for m, fr in enumerate(done):
            last = m == len(done) - 1 and f["stage"] in ("try", "decide")
            keep = fr["decision"] if (not last or f["stage"] == "decide") else None
            color = "#2E7D32" if keep else ("#C62828" if keep is False else "#555")
            ax_v.plot([m, m + 1], [fr["vdac"]] * 2, color=color, lw=3)
            ax_v.annotate(f"b{fr['bit']}", (m + 0.5, fr["vdac"]), textcoords="offset points",
                          xytext=(0, 6), ha="center", fontsize=9)
        ax_v.set_xlim(0, n)
        ax_v.set_ylim(-0.05 * model.vref, 1.05 * model.vref)
        ax_v.set_xticks(range(n + 1))
        ax_v.set_xlabel("bit-trial cycle")
        ax_v.set_ylabel("DAC voltage [V]")
        ax_v.set_title("Binary search: DAC voltage vs. input")
        ax_v.grid(alpha=0.3)
        ax_v.legend(loc="upper right", fontsize=9)

        # --- CDAC bottom-plate connections ---
        x = 0.0
        for j in order:
            w = widths[j] / total
            conn = cap_conn(f, j)
            ax_c.add_patch(Rectangle((x, 0.35), w * 0.92, 0.3, color=COLORS[conn]))
            ax_c.text(x + w * 0.46, 0.2, labels[j], ha="center", va="top", fontsize=8)
            ax_c.text(x + w * 0.46, 0.5, conn.upper(), ha="center", va="center",
                      fontsize=7, color="white", rotation=90 if w < 0.08 else 0)
            x += w
        ax_c.plot([0, 1], [0.72, 0.72], color="k", lw=2)
        ax_c.text(0.5, 0.78, "top plate -> comparator", ha="center", fontsize=9)
        ax_c.set_xlim(0, 1)
        ax_c.set_ylim(0, 1)
        ax_c.axis("off")
        ax_c.set_title("CDAC bottom-plate switches")

        # --- explanation text ---
        ax_t.axis("off")
        bits_so_far = " ".join(_bit_symbol(f, i) for i in range(n - 1, -1, -1))
        if f["stage"] == "sample":
            msg = (f"SAMPLE: all bottom plates track Vin, top plate held at Vcm = {model.vcm:.2f} V.\n"
                   f"The charge Q = (Vcm - Vin)*Ctot now stores the input. LSB = {lsb*1e3:.1f} mV.")
        elif f["stage"] == "try":
            msg = (f"TRY bit b{f['bit']}: switch C{f['bit']} bottom plate to Vref -> "
                   f"DAC = {f['vdac']:.3f} V.  Comparator checks: is DAC < Vin ?")
        elif f["stage"] == "decide":
            ok = f["decision"]
            msg = (f"DECIDE b{f['bit']} = {int(ok)}: DAC ({f['vdac']:.3f} V) "
                   f"{'<' if ok else '>'} Vin ({vin:.3f} V) -> "
                   f"{'keep C' + str(f['bit']) + ' on Vref' if ok else 'return C' + str(f['bit']) + ' to GND'}.")
        else:
            msg = (f"DONE: output code = {code} (0b{code:0{n}b}).  "
                   f"Ideal code = floor(Vin/LSB) = {int(min(vin / lsb, 2**n - 1))}.")
        ax_t.text(0.01, 0.75, msg, fontsize=11, va="top", family="monospace")
        ax_t.text(0.01, 0.12, f"bits (MSB..LSB): {bits_so_far}", fontsize=13, weight="bold")
        fig.suptitle(f"{n}-bit charge-redistribution SAR ADC - step {k + 1}/{len(frames)}", fontsize=13)
        return []

    anim = FuncAnimation(fig, draw, frames=len(frames), interval=1000 / fps, blit=False)
    if path:
        anim.save(path, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return anim
