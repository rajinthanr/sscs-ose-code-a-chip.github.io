#!/usr/bin/env python3
"""Copy the small result files of long runs (6/8-bit flows, sweeps, SPICE MC) from build/ to results/
and make the resolution-scaling table and plot. results/ is committed so the notebook can show them."""

import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

B, R = Path("build"), Path("results")
FLOW_FILES = ["summary.json", "report.md", "sizing.md", "waveforms.png", "transfer.png", "fft.png",
              "inl_dnl_histogram.png", "inl_dnl_transitions.png", "comparator_offset.png", "mc_linearity.png"]


def main():
    R.mkdir(exist_ok=True)
    rows = []
    for n in range(4, 9):
        src = B / f"{n}bit"
        if not (src / "summary.json").exists():
            continue
        dst = R / f"{n}bit"
        dst.mkdir(exist_ok=True)
        for f in FLOW_FILES:
            if (src / f).exists():
                shutil.copy2(src / f, dst / f)
        sw = src / "sweeps"
        if sw.exists():
            (dst / "sweeps").mkdir(exist_ok=True)
            for f in sw.iterdir():
                if f.is_file() and f.suffix in (".json", ".md", ".png"):
                    shutil.copy2(f, dst / "sweeps" / f.name)
        s = json.loads((src / "summary.json").read_text())
        d = json.loads((src / "design.json").read_text())
        rows.append(dict(bits=n, fs=s["spec"]["fs"], enob=s["dynamic"]["enob"],
                         ideal_enob=s["dynamic"]["ideal_model_enob"], sndr=s["dynamic"]["sndr_db"],
                         dnl=s["static"].get("dnl_t_max", s["static"]["dnl_max"]),
                         inl=s["static"].get("inl_t_max", s["static"]["inl_max"]),
                         missing=s["static"]["missing_codes"], offset=s["static"]["offset_lsb"],
                         p_uw=s["power"]["p_total"] * 1e6, e_pj=s["power"]["energy_per_conv"] * 1e12,
                         fom_fj=s["power"]["walden_fom_J"] * 1e15, ctot_ff=d["cu"]["c_total"] * 1e15,
                         cu_ff=d["cu"]["c"] * 1e15, w_in=d["cmp"]["w_in"],
                         mc_dnl_p99=s["mc"]["dnl_p99"], runtime_min=s["runtime_s"] / 60))
    if not rows:
        print("no results found in build/")
        return
    (R / "scaling.json").write_text(json.dumps(rows, indent=1))
    keys = list(rows[0])
    md = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    md += ["| " + " | ".join(f"{r[k]:.3g}" if isinstance(r[k], float) else str(r[k]) for k in keys) + " |"
           for r in rows]
    (R / "scaling.md").write_text("\n".join(md) + "\n")

    n = [r["bits"] for r in rows]
    fig, ax = plt.subplots(2, 2, figsize=(10, 7))
    ax[0, 0].plot(n, [r["enob"] for r in rows], "o-", label="SPICE")
    ax[0, 0].plot(n, [r["ideal_enob"] for r in rows], "k--", label="ideal quantizer")
    ax[0, 0].set_ylabel("ENOB [bit]")
    ax[0, 0].legend()
    ax[0, 1].semilogy(n, [r["ctot_ff"] for r in rows], "o-", label="C_total [fF]")
    ax[0, 1].semilogy(n, [r["p_uw"] for r in rows], "s-", label="power [uW]")
    ax[0, 1].legend()
    ax[1, 0].plot(n, [r["dnl"] for r in rows], "o-", label="max |DNL| (nominal)")
    ax[1, 0].plot(n, [r["inl"] for r in rows], "s-", label="max |INL| (nominal)")
    ax[1, 0].plot(n, [r["mc_dnl_p99"] for r in rows], "^--", label="DNL 99th pct (mismatch MC)")
    ax[1, 0].set_ylabel("LSB")
    ax[1, 0].legend(fontsize=8)
    ax[1, 1].plot(n, [r["fom_fj"] for r in rows], "o-")
    ax[1, 1].set_ylabel("Walden FoM [fJ/conv-step]")
    for a in ax.flat:
        a.set_xlabel("resolution N [bit]")
        a.grid(alpha=0.3, which="both")
    fig.suptitle("SARGen: one generator, resolution 4 to 8 bit (SKY130, transistor level, pre-layout)")
    fig.tight_layout()
    fig.savefig(R / "scaling.png", dpi=130)
    print((R / "scaling.md").read_text())


if __name__ == "__main__":
    main()
