"""SKY130 PDK PCells, generated with magic's device generator (the foundry-supplied PCell code)."""

import os
import subprocess
from pathlib import Path

PDK_ROOT = Path(os.environ.get("PDK_ROOT", "/foss/pdks"))
MAGICRC = PDK_ROOT / "sky130A" / "libs.tech" / "magic" / "sky130A.magicrc"
CACHE = Path(os.environ.get("SARGEN_PCELL_CACHE", "build/pcell")).resolve()


def mim_cap(w, l, name=None):
    """GDS of sky130_fd_pr__cap_mim_m3_1 (w x l um) from the PDK PCell; returns (path, cell name).

    Layers drawn by the PCell: met3 bottom plate, capm, via3 + met4 top contact (label C1) and a
    via3 + met4 bottom-plate contact strip (label C2)."""
    name = name or f"mim_{w:g}x{l:g}".replace(".", "p")
    CACHE.mkdir(parents=True, exist_ok=True)
    gds = CACHE / f"{name}.gds"
    if not gds.exists():
        tcl = CACHE / f"{name}.tcl"
        tcl.write_text(f"""crashbackups stop
magic::gencell sky130::sky130_fd_pr__cap_mim_m3_1 xc w {w} l {l} nx 1 ny 1
foreach c [cellname list allcells] {{ if {{[string match "sky130_fd_pr__cap_mim_m3_1*" $c]}} {{ set cap $c }} }}
cellname rename $cap {name}
load {name}
gds write {gds}
quit -noprompt
""")
        r = subprocess.run(["magic", "-dnull", "-noconsole", "-rcfile", str(MAGICRC), str(tcl)],
                           cwd=CACHE, capture_output=True, text=True, timeout=300)
        if not gds.exists():
            raise RuntimeError(f"PCell generation failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return gds, name


def import_pcell(gds, name, drop_layers=((235, 4), (71, 5))):
    """Import a PCell GDS into gdsfactory, dropping magic's boundary and the PCell text labels (C1/C2),
    which would otherwise give every cell of an array identically named nets."""
    import gdsfactory as gf
    c = gf.import_gds(gds, cellname=name)
    c = c.flatten()
    if drop_layers:
        c = c.remove_layers(layers=list(drop_layers))
    c.name = f"{name}_pdk"
    return c
