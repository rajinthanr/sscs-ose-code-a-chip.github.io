"""CDAC unit cell: one MIM unit capacitor with its own bottom-plate switch, built for abutment (SKY130).

    y ^  met4 top-plate strap           edge to edge, above the cap (no met5: TinyTapeout power grid)
         p-tap (vss) / n-tap (vdd)      MIM unit cap = SKY130 PDK PCell (C1 top contact, C2 bottom strip)
         vdd, vref, vss rails (met2)    static rails: the only wiring under the top-plate strap
         vin rail (met2)                below the cap, so the sampled input does not couple to the top plate
         [Mdn][Msn] | [Msp][Mdp]        gLayout fets: gate bar down, inner bar = plate, outer bar = supply
         control rails (met2, K tracks) identical in every cell of a row; each gate drops a via1 on its rail
       x ->  NMOS side at x = 0 ........ PMOS side and n-well at x = W

Rails and the top-plate strap run from edge to edge, so neighbouring cells connect by abutment.  The cell is
mirrored left/right in an array, so two PMOS sides share one n-well and two NMOS sides share spacing.
Only the via positions of the four gates differ between cells, so every unit is geometrically identical.
"""

from .cdac import M2_PAD, M3_PAD, MET2, MET3, MET4, VIA, VIA2, snap

CAPM = (89, 44)
M4_SPACE = 0.30                       # met4 spacing (strap to the PCell's C2 strip)
C1_STUB_W = 0.60                      # met4 stub from the PCell top contact C1 up to the strap
from .cell import DIFF, MET1, NWELL, VIA1, V1, Dev, _make_device

NSDM, PSDM = (93, 44), (94, 20)
LVTN = (125, 44)
CTRL_PITCH, CTRL_W = 0.34, 0.14       # control rails (met2, min width); via1 pads widen to 0.26 at the via
SUP_PITCH, SUP_W = 0.40, 0.20         # supply rails
M1_W = 0.23                           # met1 stub width
V1_M1 = (0.27, 0.32)                  # met1 pad around via1 for a vertical stub (x, y)
V1_M2 = (0.32, 0.26)                  # met2 pad around via1 on a horizontal rail (x, y)
STRAP_W = 0.80
SUPPLY = ["vin", "vss", "vref", "vdd"]   # bottom to top; vin lowest (dynamic), the rest static
# SKY130 rules used to pack the devices from their real layer extents (not gLayout's bounding boxes)
R_DIFF_SP, R_LI_SP, R_NDIFF_NWELL, R_NWELL_PDIFF, R_LVT_GATE = 0.27, 0.17, 0.34, 0.18, 0.24
R_LVTN_SP = 0.38                      # lvtn spacing; lvtn must not straddle the n-well (MR_lvtn.OVL.2)
CAPM11 = 1.34                         # capm to unrelated met3
VIA2_CAPM = 0.20                      # via2 clearance from a capm edge (inside or outside)


def cell_devices(design, gates, tag="u"):
    """gates: dict en/enb/pg/ng -> net names."""
    from ..pdk import TG_FLAVORS
    sw, drv = design["sw"], design["drv"]
    fl = sw.get("flavor", "lvt")
    ln, lp = TG_FLAVORS[fl][1], TG_FLAVORS[fl][3]
    p = f"p_{tag}"
    kw = dict(fingers=1, tie=False)
    return [Dev(f"Mdn_{tag}", "n", drv["wn"], 0.15, "vss", gates["ng"], p, **kw),
            Dev(f"Msn_{tag}", "n", sw["in_wn"], ln, "vin", gates["en"], p, flavor=fl, **kw),
            Dev(f"Msp_{tag}", "p", sw["in_wp"], lp, "vin", gates["enb"], p, flavor=fl, **kw),
            Dev(f"Mdp_{tag}", "p", drv["wp"], 0.15, "vref", gates["pg"], p, **kw)]


def _ext(comp, layer):
    pts = [pt for poly in comp.get_polygons(by_spec=layer) for pt in poly]
    if not pts:
        return None
    return min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)


class UnitCellPlan:
    """Geometry shared by every cell of an array, packed from real layer extents and SKY130 rules."""

    def __init__(self, design, n_ctrl):
        from .pcell import import_pcell, mim_cap
        proto = cell_devices(design, dict(en="a", enb="b", pg="c", ng="d"), "proto")
        self.devs = proto
        self.comps = [_make_device(d) for d in proto]
        self.w = [c.bbox[1][0] - c.bbox[0][0] for c in self.comps]
        self.h = [c.bbox[1][1] - c.bbox[0][1] for c in self.comps]
        self.inner = [c.ports["multiplier_0_source_W"].center[1] for c in self.comps]   # unrotated
        diff = [_ext(c, DIFF) for c in self.comps]
        li = [_ext(c, (67, 20)) for c in self.comps]
        lvt = [_ext(c, LVTN) for c in self.comps]
        poly = [_ext(c, (66, 20)) for c in self.comps]
        imp = [_ext(c, NSDM) or _ext(c, PSDM) for c in self.comps]
        nw = [_ext(c, NWELL) for c in self.comps]
        self.imp = imp

        def pitch(a, b):
            """centre distance device a -> device b (b to the right)."""
            if proto[a].kind != proto[b].kind:              # NMOS (a) next to the PMOS n-well (b)
                d = diff[a][1] + R_NDIFF_NWELL - nw[b][0]
                if lvt[a]:                                  # NMOS lvtn fully outside the n-well
                    d = max(d, lvt[a][1] + 0.05 - nw[b][0])
                if lvt[a] and lvt[b]:
                    d = max(d, lvt[a][1] + R_LVTN_SP - lvt[b][0])
            else:
                d = max(diff[a][1] - diff[b][0] + R_DIFF_SP, li[a][1] - li[b][0] + R_LI_SP)
                if lvt[a] and not lvt[b]:
                    d = max(d, lvt[a][1] - poly[b][0] + R_LVT_GATE)
                if lvt[b] and not lvt[a]:
                    d = max(d, poly[a][1] - lvt[b][0] + R_LVT_GATE)
            return snap(d + 0.025)

        # mirrored neighbours face the same device type: half the self-pitch to each cell edge
        e_left = max(pitch(0, 0) / 2, -imp[0][0])
        e_right = max(pitch(3, 3) / 2, imp[3][1])
        self.xc = [snap(e_left)]
        for k in range(1, 4):
            self.xc.append(snap(self.xc[-1] + pitch(k - 1, k)))
        self.W = snap(self.xc[3] + e_right)
        self.lvt_ext = lvt
        self.diff = diff

        self.n_ctrl = n_ctrl
        self.ctrl_y = [snap(0.25 + i * CTRL_PITCH) for i in range(n_ctrl)]
        y_ctrl_top = self.ctrl_y[-1] + CTRL_W / 2
        self.y_inner = snap(y_ctrl_top + 0.40 + max(o + h / 2 for o, h in zip(self.inner, self.h)))
        self.yc = [snap(self.y_inner - o) for o in self.inner]                          # device centres
        self.dev_top = max(y + e[3] for y, e in zip(self.yc, li))
        self.sup_y = {s: snap(self.dev_top + 0.40 + i * SUP_PITCH) for i, s in enumerate(SUPPLY)}

        # MIM unit cap = SKY130 PDK PCell, stacked over the switch transistors
        side = design["cu"]["side"]
        self.unit = import_pcell(*mim_cap(side, side))
        ub = self.unit.bbox
        self.cap_x0, self.cap_x1, self.cap_y0, self.cap_y1 = ub[0][0], ub[1][0], ub[0][1], ub[1][1]
        cm = _ext(self.unit, CAPM)
        self.capm_x0, self.capm_x1, self.capm_y0, self.capm_y1 = cm
        self.c1_dx = (cm[0] + cm[1]) / 2                        # PCell top contact C1 sits on the capm
        m4 = [p for p in self.unit.get_polygons(by_spec=MET4)]
        self.c2_top = max(pt[1] for poly in m4 for pt in poly)  # top of the PCell's met4 (C2 strip)
        # cap position: lowest y (smallest cell) whose met4 strap clears the vin rail, then the most centred x;
        # rules: capm.11 against both mirrored neighbours, every inner-bar via2 fully inside the capm or
        # >= VIA2_CAPM away from it (capm.8), plate inside the cell
        vin_top = self.sup_y["vin"] + SUP_W / 2
        strap_off = self.c2_top + 0.30 + STRAP_W / 2
        bus = (self.xc[0] - M3_PAD / 2, self.xc[3] + M3_PAD / 2)
        rdx = (cm[1] + self.cap_x1) / 2                 # plate via2 + riser: in the PCell contact extension

        def legal(x, y):
            capm = (x + cm[0], x + cm[1], y + cm[2], y + cm[3])
            left_unrel = max(-(x + self.cap_x0), -bus[0])
            right_unrel = min(2 * self.W - (x + self.cap_x1), 2 * self.W - bus[1])
            if capm[0] - left_unrel < CAPM11 or right_unrel - capm[1] < CAPM11:
                return False
            if x + self.cap_x0 < 0 or x + self.cap_x1 > self.W:
                return False
            m, h = VIA2_CAPM, VIA / 2                    # magic capm.8: no via2 under (or near) a capm
            vx = x + rdx
            if not (vx - h - m >= capm[1] or vx + h + m <= capm[0]):
                return False
            if not (self.xc[0] <= vx <= self.xc[3]):         # must land on the met2 plate bus
                return False
            return True

        y = snap(vin_top + 0.05 + STRAP_W / 2 - strap_off)
        found = None
        while found is None and y < self.y_inner + 6:
            xs_ok = [round(i * 0.05, 3) for i in range(int(self.W / 0.05) + 1) if legal(round(i * 0.05, 3), y)]
            if xs_ok:
                found = (min(xs_ok, key=lambda v: abs(v - self.W / 2)), y)
            y = round(y + 0.05, 3)
        assert found, "no legal cap position"
        self.cap_cx, self.cap_cy = snap(found[0]), snap(found[1])
        self.strap_y = snap(self.cap_cy + strap_off)
        # single via2 + met3 riser from the met2 plate bus into the plate, outside the capm
        self.riser_x = snap(self.cap_cx + rdx)
        # body taps under the vss / vdd rails, between the devices
        self.ptap_x = snap((self.xc[0] + self.xc[1]) / 2)
        self.ntap_x = snap((self.xc[2] + self.xc[3]) / 2)
        top_y = max(self.strap_y + STRAP_W / 2, self.sup_y["vdd"] + SUP_W / 2, self.sup_y["vdd"] + 0.205 + 0.18)
        self.H = snap(top_y + 0.30)


def draw_cell(top, plan, x0, y0, mirror, rails, gates, tag, design):
    """Draw one cell into component `top` at (x0, y0); `rails` = control rail names (bottom to top).
    Returns reference-netlist lines for LVS."""
    from gdsfactory.components import rectangle
    from glayout import sky130, via_stack

    from ..pdk import mos
    from .cell import model_name

    W = plan.W

    def X(x):                       # local x -> layout x (mirrored about the cell centre)
        return x0 + (W - x if mirror else x)

    def rect(xa, ya, xb, yb, layer):
        xa, xb = sorted((X(xa), X(xb)))
        ya, yb = y0 + min(ya, yb), y0 + max(ya, yb)
        xa, ya, xb, yb = snap(xa), snap(ya), snap(xb), snap(yb)
        if xb - xa > 0 and yb - ya > 0:
            r = top << rectangle(size=(snap(xb - xa), snap(yb - ya)), layer=layer)
            r.move((xa, ya))

    def v1(x, y, pad_m1, pad_m2):
        rect(x - pad_m1[0] / 2, y - pad_m1[1] / 2, x + pad_m1[0] / 2, y + pad_m1[1] / 2, MET1)
        rect(x - V1 / 2, y - V1 / 2, x + V1 / 2, y + V1 / 2, VIA1)
        rect(x - pad_m2[0] / 2, y - pad_m2[1] / 2, x + pad_m2[0] / 2, y + pad_m2[1] / 2, MET2)

    def v2(x, y):
        rect(x - M2_PAD / 2, y - M2_PAD / 2, x + M2_PAD / 2, y + M2_PAD / 2, MET2)
        rect(x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2, VIA2)
        rect(x - M3_PAD / 2, y - M3_PAD / 2, x + M3_PAD / 2, y + M3_PAD / 2, MET3)

    devs = cell_devices(design, gates, tag)
    ctrl_y = dict(zip(rails, plan.ctrl_y))
    lines = []
    for k, (dv, comp) in enumerate(zip(devs, plan.comps)):
        ref = top << comp
        if mirror:
            ref.mirror((0, 0), (0, 1))
        ref.move((snap(X(plan.xc[k])), snap(y0 + plan.yc[k])))
        p = ref.ports

        def cx(name):
            return (p[f"multiplier_0_{name}_W"].center[0] + p[f"multiplier_0_{name}_E"].center[0]) / 2

        def lx(xl):                 # layout x -> local x
            return (W - (xl - x0)) if mirror else (xl - x0)

        gx, gy = lx(cx("gate")), p["multiplier_0_gate_W"].center[1] - y0
        ix, iy = lx(cx("source")), p["multiplier_0_source_W"].center[1] - y0
        ox, oy = lx(cx("drain")), p["multiplier_0_drain_W"].center[1] - y0
        # gate -> its control rail (the only per-cell difference)
        yr = ctrl_y[dv.g]
        rect(gx - M1_W / 2, yr, gx + M1_W / 2, gy, MET1)
        v1(gx, yr, V1_M1, V1_M2)
        # outer bar -> supply rail
        ys = plan.sup_y[dv.d]
        rect(ox - M1_W / 2, oy, ox + M1_W / 2, ys, MET1)
        v1(ox, ys, V1_M1, V1_M2)
        # inner bar -> met2 plate bus (met1 pad along the bar); no via2 here (it would sit under the capm)
        v1(ix, iy, (V1_M1[1], V1_M1[0]), V1_M2)
        lines.append(mos(dv.name, dv.d, dv.g, dv.s, "vss" if dv.kind == "n" else "vdd", model_name(dv), dv.w, dv.l))
    # plate bus (met2) through the four inner via1s, one via2 beside the capm, met3 riser into the plate
    xs = sorted(plan.xc)
    rect(xs[0] - V1_M2[0] / 2, plan.y_inner - V1_M2[1] / 2, xs[-1] + V1_M2[0] / 2, plan.y_inner + V1_M2[1] / 2, MET2)
    v2(plan.riser_x, plan.y_inner)
    capref = top << plan.unit
    if mirror:                      # the PDK PCell is asymmetric (C1 left, C2 strip right): mirror it too
        capref.mirror((0, 0), (0, 1))
    capref.move((snap(X(plan.cap_cx)), snap(y0 + plan.cap_cy)))
    rect(plan.riser_x - 0.25, plan.y_inner, plan.riser_x + 0.25, plan.cap_cy, MET3)
    side = design["cu"]["side"]
    lines.append(f"XC_{tag} top p_{tag} sky130_fd_pr__cap_mim_m3_1 W={side} L={side} MF=1")
    # rails edge to edge
    for y in plan.ctrl_y:
        rect(0, y - CTRL_W / 2, W, y + CTRL_W / 2, MET2)
    for y in plan.sup_y.values():
        rect(0, y - SUP_W / 2, W, y + SUP_W / 2, MET2)
    # top plate (all met4, no met5): stub from the PCell top contact C1 up past the C2 strip, then a strap
    # edge to edge over the static rails only
    c1x = plan.cap_cx + plan.c1_dx
    rect(c1x - C1_STUB_W / 2, plan.cap_cy, c1x + C1_STUB_W / 2, plan.strap_y, MET4)
    rect(0, plan.strap_y - STRAP_W / 2, W, plan.strap_y + STRAP_W / 2, MET4)
    # body taps directly under their rails (via1 straight up)
    tap = via_stack(sky130, "active_tap", "met2")
    for tx, net, imp in ((plan.ptap_x, "vss", PSDM), (plan.ntap_x, "vdd", NSDM)):
        ty = plan.sup_y[net]
        t = top << tap
        t.move((snap(X(tx)), snap(y0 + ty)))
        rect(tx - 0.34, ty - 0.34, tx + 0.34, ty + 0.34, imp)
        v1(tx, ty, V1_M1, V1_M2)
    # n-well: PMOS pair + n-tap, out to the PMOS-side cell edge (shared with the mirrored neighbour)
    nx0 = plan.xc[2] + plan.diff[2][0] - R_NWELL_PDIFF
    rect(nx0, plan.yc[2] - plan.h[2] / 2, W, plan.sup_y["vdd"] + 0.205 + 0.18, NWELL)
    # merge the implants of same-type neighbours (tight packing leaves slivers < 0.38 um otherwise)
    # edge implants overlap 0.05 um past the cell edge so mirrored neighbours always merge (no slivers)
    rect(-0.05, plan.yc[0] + plan.imp[0][2], plan.xc[0] + plan.imp[0][0] + 0.10, plan.yc[0] + plan.imp[0][3], NSDM)
    rect(plan.xc[3] + plan.imp[3][1] - 0.10, plan.yc[3] + plan.imp[3][2], W + 0.05, plan.yc[3] + plan.imp[3][3], PSDM)
    for a, b, lay in ((0, 1, NSDM), (2, 3, PSDM)):
        ea, eb = plan.imp[a], plan.imp[b]
        ylo = max(plan.yc[a] + ea[2], plan.yc[b] + eb[2])
        yhi = min(plan.yc[a] + ea[3], plan.yc[b] + eb[3])
        rect(plan.xc[a] + ea[1] - 0.01, ylo, plan.xc[b] + eb[0] + 0.01, yhi, lay)
    return lines


def build_unit_cell(design, rails, gates, name="cdac_unit"):
    """A single unit cell (flattened), its reference netlist and pins."""
    from gdsfactory import Component
    from .cdac import LBL, PIN
    plan = UnitCellPlan(design, len(rails))
    top = Component(name + "_hier")
    lines = draw_cell(top, plan, 0.0, 0.0, False, rails, gates, "u", design)
    for net, y in list(zip(rails, plan.ctrl_y)) + list(plan.sup_y.items()):
        _pin(top, net, 0.0, y, MET2)
    _pin(top, "top", 0.0, plan.strap_y, MET4)
    top = top.flatten()
    top.name = name
    pins = ["top"] + list(dict.fromkeys(list(plan.sup_y) + rails))
    ref = "\n".join([f".subckt {name} {' '.join(pins)}"] + lines + [f".ends {name}"]) + "\n"
    return top, plan, ref


def _pin(top, net, x, y, layer):
    from gdsfactory.components import rectangle
    from .cdac import LBL, PIN
    r = top << rectangle(size=(0.3, 0.16), layer=PIN[layer])
    r.move((snap(x + 0.05), snap(y - 0.08)))
    top.add_label(text=net, position=(snap(x + 0.2), snap(y)), layer=LBL[layer])


def build_abut_test(design, rails, gate_maps, cols=2, rows=2, name="cdac_unit_2x2"):
    """rows x cols abutted cells (mirrored alternate columns) to prove the cell tiles DRC/LVS-clean."""
    from gdsfactory import Component
    plan = UnitCellPlan(design, len(rails))
    top = Component(name + "_hier")
    lines = []
    k = 0
    for r in range(rows):
        for c in range(cols):
            lines += draw_cell(top, plan, c * plan.W, r * plan.H, c % 2 == 1, rails, gate_maps[k % len(gate_maps)],
                               f"{r}_{c}", design)
            k += 1
    for r in range(rows):
        for net, y in list(zip(rails, plan.ctrl_y)) + list(plan.sup_y.items()):
            _pin(top, net, 0.0, r * plan.H + y, MET2)
    _pin(top, "top", 0.0, plan.strap_y, MET4)
    top = top.flatten()
    top.name = name
    pins = ["top"] + list(dict.fromkeys(list(plan.sup_y) + rails))
    ref = "\n".join([f".subckt {name} {' '.join(pins)}"] + lines + [f".ends {name}"]) + "\n"
    return top, plan, ref


def rowwise_grid(bits):
    """Common-centroid assignment that keeps few bits per row (few control rails).

    Point-symmetric cell pairs are taken row by row from the outside in; groups are dealt largest first,
    so the MSB fills the outer row pair, smaller bits share the inner rows.  Every group is a set of
    point-symmetric pairs (centroid exactly at the array centre); the LSB and the termination unit share
    the last pair."""
    from .cdac import array_shape
    R, C = array_shape(bits)
    pairs, seen = [], set()
    for r in range(R):
        for c in range(C):
            if (r, c) not in seen:
                m = (R - 1 - r, C - 1 - c)
                seen |= {(r, c), m}
                pairs.append(((r, c), m))
    grid = [[None] * C for _ in range(R)]
    k = 0
    for g in reversed(range(1, bits)):
        for _ in range(2 ** (g - 1)):
            (a, b) = pairs[k]
            grid[a[0]][a[1]] = grid[b[0]][b[1]] = g
            k += 1
    (a, b) = pairs[k]
    grid[a[0]][a[1]], grid[b[0]][b[1]] = 0, "d"
    return grid


def unit_gates(g, bits):
    if g == "d":                        # termination unit: Vref driver held off, ground driver on phigb
        return dict(en="phig", enb="phigb", pg="vdd", ng="phigb")
    en, enb = ("phis", "phisb") if g == bits - 1 else ("phig", "phigb")
    return dict(en=en, enb=enb, pg=f"pg_{g}", ng=f"ng_{g}")


PHASES = ["phis", "phisb", "phig", "phigb", "vdd"]


def build_unit_array(design, bits, name=None, grid=None):
    """CDAC with per-unit switches: abutted unit cells (mirrored alternate columns), edge trunks, left spine.
    Returns (Component, info, reference netlist)."""
    from gdsfactory import Component
    from .cdac import LBL, PIN, centroid_grid

    grid = grid or rowwise_grid(bits)
    R, C = len(grid), len(grid[0])
    rails_row = []
    for r in range(R):
        sig = set()
        for g in grid[r]:
            sig |= set(unit_gates(g, bits).values())
        rails_row.append([s for s in PHASES if s in sig] + sorted(s for s in sig if s not in PHASES))
    K = max(len(x) for x in rails_row)
    rails_row = [x + [None] * (K - len(x)) for x in rails_row]   # unused slots stay empty rails
    plan = UnitCellPlan(design, K)
    name = name or f"cdacu{bits}b"
    top = Component(name + "_hier")

    def rect(xa, ya, xb, yb, layer):
        from gdsfactory.components import rectangle
        xa, xb, ya, yb = snap(min(xa, xb)), snap(max(xa, xb)), snap(min(ya, yb)), snap(max(ya, yb))
        r = top << rectangle(size=(snap(xb - xa), snap(yb - ya)), layer=layer)
        r.move((xa, ya))

    def v2(x, y):
        rect(x - M2_PAD / 2, y - M2_PAD / 2, x + M2_PAD / 2, y + M2_PAD / 2, MET2)
        rect(x - VIA / 2, y - VIA / 2, x + VIA / 2, y + VIA / 2, VIA2)
        rect(x - M3_PAD / 2, y - M3_PAD / 2, x + M3_PAD / 2, y + M3_PAD / 2, MET3)

    lines = []
    for r in range(R):
        y0 = (R - 1 - r) * plan.H
        names = [x if x else f"_nc{r}_{i}" for i, x in enumerate(rails_row[r])]
        for c in range(C):
            lines += draw_cell(top, plan, c * plan.W, y0, c % 2 == 1, names, unit_gates(grid[r][c], bits),
                               f"{r}_{c}", design)
    Wa, Ha = C * plan.W, R * plan.H

    # rails -> trunks: supplies and phases on the left (static or slow), bit controls on the right
    rail_pos = []                      # (net, y)
    for r in range(R):
        y0 = (R - 1 - r) * plan.H
        rail_pos += [(n, y0 + y) for n, y in zip(rails_row[r], plan.ctrl_y) if n]
        rail_pos += [(n, y0 + y) for n, y in plan.sup_y.items()]
    nets = list(dict.fromkeys(SUPPLY + PHASES + sorted({n for n, _ in rail_pos} - set(SUPPLY + PHASES))))
    nets = [n for n in nets if any(n == m for m, _ in rail_pos)]
    left = [n for n in nets if n in SUPPLY or n in PHASES]
    right = [n for n in nets if n not in left]
    spine_x = -1.2                                         # top-plate spine just outside the cells
    tx = {n: snap(spine_x - 1.6 - i * 0.9) for i, n in enumerate(left)}
    tx.update({n: snap(Wa + 1.2 + i * 0.9) for i, n in enumerate(right)})
    for n, y in rail_pos:
        w = SUP_W if n in SUPPLY else CTRL_W
        xa, xb = (tx[n], 0.0) if n in left else (Wa, tx[n])
        rect(xa - M2_PAD / 2, y - w / 2, xb + M2_PAD / 2, y + w / 2, MET2)
        v2(tx[n], y)
    for n in nets:
        ys = [y for m, y in rail_pos if m == n]
        lo, hi = min(ys) - M3_PAD / 2, max(max(ys) + M3_PAD / 2, min(ys) + 1.0)
        rect(tx[n] - 0.25, lo, tx[n] + 0.25, hi, MET3)
        _pin(top, n, tx[n] - 0.2, hi - 0.3, MET3)
    # top plate: straps extend to the left spine (met4); the spine crosses only rail stubs at the edge
    for r in range(R):
        y = (R - 1 - r) * plan.H + plan.strap_y
        rect(spine_x - STRAP_W / 2, y - STRAP_W / 2, 0.0, y + STRAP_W / 2, MET4)
    ys = [(R - 1 - r) * plan.H + plan.strap_y for r in range(R)]
    rect(spine_x - STRAP_W / 2, min(ys) - STRAP_W / 2, spine_x + STRAP_W / 2, max(ys) + STRAP_W / 2, MET4)
    _pin(top, "top", spine_x - 0.15, max(ys), MET4)

    top = top.flatten()
    top.name = name
    pins = ["top"] + nets
    ref = "\n".join([f".subckt {name} {' '.join(pins)}"] + lines + [f".ends {name}"]) + "\n"
    bb = top.bbox
    info = dict(bits=bits, grid=grid, cell=(plan.W, plan.H), ctrl_rails=K, rails_per_row=rails_row,
                width=float(bb[1][0] - bb[0][0]), height=float(bb[1][1] - bb[0][1]), pins=pins)
    return top, info, ref
