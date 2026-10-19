"""SKY130 PDK access: model library, device cards and PDK-derived constants."""

import os
import re
from pathlib import Path

PDK_ROOT = Path(os.environ.get("PDK_ROOT", "/foss/pdks"))
PDK = "sky130A"
NG_LIB = PDK_ROOT / PDK / "libs.tech/ngspice/sky130.lib.spice"
MIM_MODEL = PDK_ROOT / PDK / "libs.ref/sky130_fd_pr/spice/sky130_fd_pr__cap_mim_m3_1.model.spice"

NFET = "sky130_fd_pr__nfet_01v8"
PFET = "sky130_fd_pr__pfet_01v8"
MIM = "sky130_fd_pr__cap_mim_m3_1"

L_MIN = 0.15          # um, 1.8 V devices
W_MIN = 0.42          # um
MIM_MIN_SIDE = 2.0    # um, practical lower bound chosen for matching/layout (rule minimum is smaller)
DIFF_EXT = 0.29       # um, source/drain extension used for AD/AS/PD/PS estimates


def lib_line(corner: str = "tt", mismatch: bool = False) -> str:
    section = f"{corner}_mm" if mismatch else corner
    return f".lib {NG_LIB} {section}"


def mim_matching_pct_um() -> float:
    """sigma(dC/C) * sqrt(W*L) in %*um, read from the SKY130 MIM model (MC_MM_SWITCH term)."""
    try:
        txt = MIM_MODEL.read_text()
        m = re.search(r"AGAUSS\(0,1\.0,1\)\*0\.01\*([0-9.]+)", txt)
        if m:
            return float(m.group(1))
    except OSError:
        pass
    return 2.8


def mos(name, d, g, s, b, model, w, l, m=1) -> str:
    """One MOSFET card with diffusion geometry filled in (single finger)."""
    ad = w * DIFF_EXT
    pd = 2 * (w + DIFF_EXT)
    return (f"X{name} {d} {g} {s} {b} {model} L={l:.3g} W={w:.4g} nf=1 "
            f"ad={ad:.4g} as={ad:.4g} pd={pd:.4g} ps={pd:.4g} "
            f"nrd={DIFF_EXT / w:.4g} nrs={DIFF_EXT / w:.4g} sa=0 sb=0 sd=0 mult={m} m={m}")


def mim(name, top, bot, w, l) -> str:
    return f"X{name} {top} {bot} {MIM} W={w:.4g} L={l:.4g} MF=1"


SPICEINIT = """set ngbehavior=hsa
set skywaterpdk
set ng_nomodcheck
set num_threads=1
option klu
"""
