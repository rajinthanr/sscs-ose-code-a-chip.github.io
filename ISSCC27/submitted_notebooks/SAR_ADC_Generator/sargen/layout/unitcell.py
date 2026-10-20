"""CDAC unit cell: one MIM unit capacitor with its own bottom-plate switch, built for abutment (SKY130).

    y ^  p-tap (vss) / n-tap (vdd)      MIM unit cap, met4 top-plate strap from edge to edge
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
from .cell import DIFF, MET1, NWELL, VIA1, V1, Dev, _make_device

NSDM, PSDM = (93, 44), (94, 20)
CTRL_PITCH, CTRL_W = 0.42, 0.17       # control rails (met2): via1 pads widen to 0.26 only at the via
SUP_PITCH, SUP_W = 0.48, 0.23         # supply rails
M1_W = 0.23                           # met1 stub width
V1_M1 = (0.27, 0.32)                  # met1 pad around via1 for a vertical stub (x, y)
V1_M2 = (0.32, 0.26)                  # met2 pad around via1 on a horizontal rail (x, y)
EDGE = 0.15                           # device bbox to cell edge (2 x EDGE between mirrored cells)
DEV_GAP = 0.30                        # between devices of one type
NP_GAP = 0.60                         # NMOS pair to PMOS pair
STRAP_W = 0.80
SUPPLY = ["vin", "vss", "vref", "vdd"]   # bottom to top; vin lowest (dynamic), the rest static


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


class UnitCellPlan:
    """Geometry shared by every cell of an array (computed once from the device sizes and K)."""

    def __init__(self, design, n_ctrl):
        from glayout import mimcap, sky130
        proto = cell_devices(design, dict(en="a", enb="b", pg="c", ng="d"), "proto")
        self.comps = [_make_device(d) for d in proto]
        self.w = [c.bbox[1][0] - c.bbox[0][0] for c in self.comps]
        self.h = [c.bbox[1][1] - c.bbox[0][1] for c in self.comps]
        self.inner = [c.ports["multiplier_0_source_W"].center[1] for c in self.comps]   # unrotated
        x = EDGE
        self.xc = []
        for k, w in enumerate(self.w):
            self.xc.append(snap(x + w / 2))
            x += w + (NP_GAP if k == 1 else DEV_GAP)
        self.W = snap(x - DEV_GAP + EDGE)
        self.n_ctrl = n_ctrl
        self.ctrl_y = [snap(0.30 + i * CTRL_PITCH) for i in range(n_ctrl)]
        y_ctrl_top = self.ctrl_y[-1] + CTRL_W / 2
        self.y_inner = snap(y_ctrl_top + 0.45 + max(o + h / 2 for o, h in zip(self.inner, self.h)))
        self.yc = [snap(self.y_inner - o) for o in self.inner]                          # device centres
        dev_top = max(y + h / 2 for y, h in zip(self.yc, self.h))
        self.sup_y = {s: snap(dev_top + 0.45 + i * SUP_PITCH) for i, s in enumerate(SUPPLY)}
        self.y_tap = snap(self.sup_y["vdd"] + SUP_W / 2 + 0.55)
        self.unit = mimcap(sky130, (design["cu"]["side"], design["cu"]["side"]))
        ub = self.unit.bbox
        self.cap_h = ub[1][1] - ub[0][1]
        cap_lo = self.sup_y["vin"] + SUP_W / 2 + 0.25          # cap (and strap) above the vin rail
        self.cap_cy = snap(cap_lo + self.cap_h / 2)
        self.cap_cx = snap((self.xc[1] + self.xc[2]) / 2)      # over the middle of the cell
        self.strap_y = self.cap_cy
        self.H = snap(max(self.cap_cy + self.cap_h / 2, self.y_tap + 0.35) + 0.30)
        self.dev_top = dev_top


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
        # inner bar -> plate bus (met1 pad along the bar)
        v1(ix, iy, (V1_M1[1], V1_M1[0]), V1_M2)
        v2(ix, iy)
        lines.append(mos(dv.name, dv.d, dv.g, dv.s, "vss" if dv.kind == "n" else "vdd", model_name(dv), dv.w, dv.l))
    # plate bus (met3) through the four inner vias, riser into the cap bottom plate
    xs = sorted(plan.xc)
    rect(xs[0] - M3_PAD / 2, plan.y_inner - M3_PAD / 2, xs[-1] + M3_PAD / 2, plan.y_inner + M3_PAD / 2, MET3)
    capref = top << plan.unit
    capref.move((snap(X(plan.cap_cx)), snap(y0 + plan.cap_cy)))
    rect(plan.cap_cx - 0.25, plan.y_inner, plan.cap_cx + 0.25, plan.cap_cy, MET3)
    side = design["cu"]["side"]
    lines.append(f"XC_{tag} top p_{tag} sky130_fd_pr__cap_mim_m3_1 W={side} L={side} MF=1")
    # rails and top-plate strap, edge to edge
    for y in plan.ctrl_y:
        rect(0, y - CTRL_W / 2, W, y + CTRL_W / 2, MET2)
    for y in plan.sup_y.values():
        rect(0, y - SUP_W / 2, W, y + SUP_W / 2, MET2)
    rect(0, plan.strap_y - STRAP_W / 2, W, plan.strap_y + STRAP_W / 2, MET4)
    # body taps above the rails: p-tap on the NMOS side, n-tap on the PMOS side
    tap = via_stack(sky130, "active_tap", "met2")
    for tx, net, imp in ((plan.xc[0], "vss", PSDM), (plan.xc[3], "vdd", NSDM)):
        t = top << tap
        t.move((snap(X(tx)), snap(y0 + plan.y_tap)))
        rect(tx - 0.34, plan.y_tap - 0.34, tx + 0.34, plan.y_tap + 0.34, imp)
        rect(tx - M1_W / 2, plan.sup_y[net], tx + M1_W / 2, plan.y_tap, MET1)
        v1(tx, plan.sup_y[net], V1_M1, V1_M2)
    # n-well: PMOS pair + n-tap, out to the PMOS-side cell edge (shared with the mirrored neighbour)
    nx0 = plan.xc[2] - plan.w[2] / 2 - 0.10
    rect(nx0, plan.yc[2] - plan.h[2] / 2 - 0.05, W, plan.y_tap + 0.55, NWELL)
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
    _pin(top, "top", plan.cap_cx, plan.strap_y, MET4)
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
    _pin(top, "top", plan.cap_cx, plan.strap_y, MET4)
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
