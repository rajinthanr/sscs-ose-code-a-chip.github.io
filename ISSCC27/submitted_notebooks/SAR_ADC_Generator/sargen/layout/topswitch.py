"""Top-plate sampling switch (transmission gate top <-> vcm) from SKY130 PDK FET PCells, in guard rings.

    vdd rail + n-tap (ring top)
    phitb comb (PMOS gates)                        gate contacts on the outer side of each row
    [vcm Mp top Mp vcm ...]                        PMOS fingers, the top node on inner shared bars
    n-tap ring segment                             | n-well
    vcm / top tracks (met2) over the ring segments  the channel carries only the two source/drain nets
    p-tap ring segment
    [vcm Mn top Mn vcm ...]                        NMOS fingers
    phit comb (NMOS gates)
    vss rail + p-tap (ring bottom)

The switch's diffusion is the floating top plate's only junction to the substrate, so the NMOS sits in a
closed p+ ring to vss and the PMOS in a closed n-tap ring to vdd (Hastings, guard rings; SKY130 latch-up
LU.2 / LU.3).  The top node goes up to met4, the CDAC top plate's layer (no met5: TinyTapeout grid).
"""

import math

from .cdac import M2_PAD, M3_PAD, MET2, MET3, MET4, VIA, VIA2, snap
from .cell import MET1, NWELL, VIA1, V1, Dev
from .strongarm import (RAIL_W, R_DIFF_TAP, TAP_H, M1_STUB, TRK, TRK_IN, WF_MAX, Row, _fe_extra, _row_draw,
                        _tap_strip)
from .unitcell import LI, MC, MCON, NSDM, PSDM, R_M1_SP, R_M2_SP, V1_M1, V1_M2, _pin, _poly

VIA3, M3_TOP = (70, 44), 0.50          # via3; met3 landing (met3.6 area 0.24 um^2)


def _fingers(name, kind, w, l, flavor, gate, side):
    """Fingers of one device, the top node on inner shared bars: vcm top vcm top ... (odd count: vcm ends)."""
    k = max(1, math.ceil(w / WF_MAX - 1e-9))
    dv = Dev(name, kind, w / k, l, "", "", "", fingers=1, tie=False, flavor=flavor)
    nodes = ["vcm" if i % 2 == 0 else "top" for i in range(k + 1)]
    return Row([(f"{name}.{i}", dv, gate, side, nodes[i], nodes[i + 1]) for i in range(k)],
               align="bot" if side == "bot" else "top")


def build_top_switch(design, name="topsw"):
    """Returns (Component, info, reference netlist).  Ports: top vcm phit phitb vdd vss."""
    from gdsfactory import Component
    from ..netlist import tg_lines
    from ..pdk import TG_FLAVORS
    sw = design["sw"]
    fl = sw.get("top_flavor", sw.get("flavor", "std"))
    _, ln, _, lp = TG_FLAVORS[fl]
    nrow = _fingers("Mttn", "n", sw["top_wn"], ln, fl, "phit", "bot")
    prow = _fingers("Mttp", "p", sw["top_wp"], lp, fl, "phitb", "top")
    nrow.center()
    prow.center()
    # NMOS drops to the upper (top) track and PMOS drops to the lower (vcm) track overlap in the channel:
    # shift the PMOS row by the least amount that keeps those apart
    nx = [x for x, n, f in nrow.bars("top")]
    px = [x for x, n, f in prow.bars("vcm")]
    gap = M1_STUB + R_M1_SP
    s_best = min((i * 0.005 * sgn for i in range(400) for sgn in (1, -1)),
                 key=lambda s_: (any(abs(a - b - s_) < gap for a in nx for b in px), abs(s_)))
    prow.shift(snap(s_best))
    for row in (nrow, prow):
        for f in row.f:
            _fe_extra(f["fe"])
    top = Component(name + "_hier")
    rect = lambda xa, ya, xb, yb, lay: _poly(top, xa, ya, xb, yb, lay)

    def box(x, y, w, h, lay):
        rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, lay)

    def v1(x, y, li=True):
        if li:
            box(x, y, MC, MC, MCON)
        box(x, y, *V1_M1, MET1)
        box(x, y, V1, V1, VIA1)
        box(x, y, *V1_M2, MET2)

    fN, fP = nrow.f[0], prow.f[0]
    # ---- vertical placement
    y_g0 = RAIL_W + R_M1_SP + V1_M1[1] / 2                         # NMOS gate comb
    yN = max(y_g0 - fN["fe"].pad_y - fN["dy"], RAIL_W / 2 + TAP_H / 2 + R_DIFF_TAP - nrow.span(0, "diff", 2))
    y_g0 = yN + fN["dy"] + fN["fe"].pad_y
    y_pseg = nrow.span(yN, "diff", 3) + R_DIFF_TAP + TAP_H / 2      # p-ring top segment (vcm track over it)
    nw0 = y_pseg + TAP_H / 2 + 0.13 + 0.05                          # n-well edge (p-tap to n-well)
    y_nseg = nw0 + 0.18 + TAP_H / 2                                 # n-ring bottom segment (top track over it)
    yP = y_nseg + TAP_H / 2 + R_DIFF_TAP - prow.span(0, "diff", 2)
    y_g1 = yP + fP["dy"] + fP["fe"].pad_y                           # PMOS gate comb
    y_vdd = max(y_g1 + V1_M1[1] / 2 + R_M1_SP, prow.span(yP, "diff", 3) + R_DIFF_TAP + TAP_H / 2 - RAIL_W / 2)
    H = y_vdd + RAIL_W
    _row_draw(top, nrow, yN)
    _row_draw(top, prow, yP)
    # ---- rings: x of the side stripes clear of every diffusion and implant
    xs = [f["x"] + f["fe"].diff[k] for row in (nrow, prow) for f in row.f for k in (0, 1)]
    xi = [f["x"] + f["fe"].imp[k] for row in (nrow, prow) for f in row.f for k in (0, 1)]
    xg = [x + s * 0.4 for row in (nrow, prow) for f in row.f for x, s in ((f["x"], -1), (f["x"], 1))]
    x_ring = max(max(abs(v) for v in xs) + R_DIFF_TAP, max(abs(v) for v in xi) + 0.13,
                 max(abs(v) for v in xg) + V1_M1[0] / 2 + 0.3) + TAP_H / 2
    X1 = x_ring + TAP_H / 2 + 0.18
    for yr, kind in ((0.0, "p"), (y_vdd, "n")):                    # outer strips under the rails
        rect(-X1, yr, X1, yr + RAIL_W, MET1)
        _tap_strip(top, -X1 + 0.2, X1 - 0.2, yr + RAIL_W / 2, kind)
    _tap_strip(top, -x_ring - TAP_H / 2, x_ring + TAP_H / 2, y_pseg, "p", mcon=False)   # inner segments
    _tap_strip(top, -x_ring - TAP_H / 2, x_ring + TAP_H / 2, y_nseg, "n", mcon=False)
    for x in (-x_ring, x_ring):
        _tap_strip(top, RAIL_W / 2, y_pseg, x, "p", vertical=True, margin=TAP_H)
        _tap_strip(top, y_nseg, y_vdd + RAIL_W / 2, x, "n", vertical=True, margin=TAP_H)
    rect(-X1, nw0, X1, H + 0.3, NWELL)
    # ---- source / drain: bars -> met1 drops -> met2 tracks over the ring segments
    y_vcm, y_top = y_pseg, y_nseg
    for row, y, up in ((nrow, yN, True), (prow, yP, False)):
        for x, n, f in row.bars():
            yb = y + f["dy"] + f["fe"].bar_y[1 if up else 0]
            ym = yb - MC / 2 if up else yb + MC / 2
            box(x, ym, MC, MC, MCON)
            box(x, ym, M1_STUB, MC + 0.12, MET1)
            yt = y_vcm if n == "vcm" else y_top
            rect(x - M1_STUB / 2, min(ym, yt), x + M1_STUB / 2, max(ym, yt), MET1)
    for net, y in (("vcm", y_vcm), ("top", y_top)):
        xs_ = sorted(x for row in (nrow, prow) for x, n, f in row.bars(net))
        clusters = [[xs_[0]]]                                       # one via per group of nearby drops
        for x in xs_[1:]:
            (clusters[-1].append(x) if x - clusters[-1][-1] < V1_M1[0] + R_M1_SP else clusters.append([x]))
        for cl in clusters:
            rect(cl[0] - M1_STUB / 2, y - V1_M1[1] / 2, cl[-1] + M1_STUB / 2, y + V1_M1[1] / 2, MET1)
            v1(snap(sum(cl) / len(cl)), y, li=False)
        rect(xs_[0] - V1_M2[0] / 2, y - TRK / 2, xs_[-1] + V1_M2[0] / 2, y + TRK / 2, MET2)
    # top -> met4 (the CDAC top plate's layer) at the track's right end; vcm pin on met2 at the left end
    xt = max(x for row in (nrow, prow) for x, n, f in row.bars("top")) + 0.6
    rect(xt - 0.6, y_top - TRK / 2, xt, y_top + TRK / 2, MET2)
    box(xt, y_top, M2_PAD, M2_PAD, MET2)
    box(xt, y_top, VIA, VIA, VIA2)
    box(xt, y_top, M3_TOP, M3_TOP, MET3)
    box(xt, y_top, 0.2, 0.2, VIA3)
    box(xt, y_top, 0.6, 0.6, MET4)
    _pin(top, "top", xt, y_top, MET4)
    xv = min(x for row in (nrow, prow) for x, n, f in row.bars("vcm"))
    _pin(top, "vcm", xv, y_vcm, MET2)
    # ---- gates: combs -> via at the comb end -> pins on met2
    for row, y, net in ((nrow, y_g0, "phit"), (prow, y_g1, "phitb")):
        xa = min(f["x"] for f in row.f) - f["fe"].pad_poly[1]
        xb = max(f["x"] for f in row.f) + 0.4
        rect(xa, y - MC / 2, xb + MC / 2, y + MC / 2, LI)
        v1(xb, y)
        rect(xb, y - TRK_IN / 2, x_ring - TAP_H / 2 - 0.3, y + TRK_IN / 2, MET2)
        _pin(top, net, xb, y, MET2)
    _pin(top, "vss", 0.0, RAIL_W / 2, MET1)
    _pin(top, "vdd", 0.0, y_vdd + RAIL_W / 2, MET1)
    top = top.flatten()
    top.name = name
    bb = top.bbox
    lines = tg_lines("Mtt", "top", "vcm", "phit", "phitb", sw["top_wn"], sw["top_wp"], fl)
    lines = [ln.replace(" 0 ", " vss ", 1) if ln.startswith("XMttn") or ln.startswith("MMttn") else ln for ln in lines]
    pins = ["top", "vcm", "phit", "phitb", "vdd", "vss"]
    ref = "\n".join([f".subckt {name} {' '.join(pins)}"] + lines + [f".ends {name}"]) + "\n"
    info = dict(width=float(bb[1][0] - bb[0][0]), height=float(bb[1][1] - bb[0][1]), flavor=fl,
                fingers=dict(n=len(nrow.f), p=len(prow.f)))
    return top, info, ref
