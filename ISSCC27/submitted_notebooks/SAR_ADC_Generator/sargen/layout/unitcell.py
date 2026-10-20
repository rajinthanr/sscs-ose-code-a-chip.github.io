"""CDAC unit cell: one MIM unit capacitor with its own bottom-plate switch, built for abutment (SKY130).

    y ^  drive rails pg_k / ng_k    met2, edge to edge   <- Mdn, Mdp gates (contact above the diffusion)
         [Mdn][Msn] | [Msp][Mdp]    SKY130 PDK FET PCells (li only), plate bus (met2) through the row
         sample rails phi*          met2, edge to edge   <- Msn, Msp gates (contact below the diffusion)
       x ->  vss ......... vin ......... vref  vdd      supplies: vertical met1 lines, edge to edge
             NMOS edge (x = 0)          PMOS edge + n-well (x = W)

The MIM unit cap (SKY130 PDK PCell) covers the whole switch; its met3 plate shields the top plate from
everything underneath.  The top plate leaves the PCell's C1 contact on a short met4 stub to a vertical met4
strap on the vss edge (no met5: TinyTapeout power grid), so the strap only crosses the rails, never runs
along one.  Cells are mirrored left/right in an array: the vss line, the p-tap and the top-plate strap are
shared on the NMOS edge, the vdd line, the n-tap and the n-well on the PMOS edge.  Rows abut vertically
(supply lines, strap and n-well run through).  The cell size is set by the MIM spacing rule capm.11
(1.34 um from capm to an unrelated met3), the switch fits underneath.  Only the via positions of the four
gates differ between cells, so every unit is geometrically identical.
"""

from .cdac import LBL, M2_PAD, M3_PAD, MET2, MET3, MET4, PIN, VIA, VIA2, snap
from .cell import DIFF, MET1, NWELL, VIA1, V1, Dev

CAPM = (89, 44)
LI, MCON, POLY = (67, 20), (67, 44), (66, 20)
NSDM, PSDM = (93, 44), (94, 20)
LVTN = (125, 44)
CTRL_PITCH, CTRL_W = 0.34, 0.14       # control rails (met2, min width); via1 pads widen to 0.26 at the via
M1_LINE = 0.23                        # vertical supply line (met1): mcon + 0.03 enclosure
MC = 0.17                             # mcon
V1_M1 = (0.27, 0.32)                  # met1 pad around mcon + via1 (x, y)
V1_M2 = (0.32, 0.26)                  # met2 pad around via1 on a horizontal rail (x, y)
STRAP_W = 0.80                        # vertical top-plate strap (met4), centred on the vss edge
STUB_W = 0.60                         # met4 stub from the PCell top contact C1 to the strap
TAP_DY = 1.0                          # body taps this far below (p-tap) / above (n-tap) the plate bus
SUPPLY = ["vss", "vin", "vref", "vdd"]
GATE_SIDE = ["top", "bot", "bot", "top"]   # Mdn, Msn, Msp, Mdp: drive gates up, sample gates down
# SKY130 rules used to pack the cell
R_DIFF_SP, R_LI_SP, R_POLY_SP, R_M1_SP = 0.27, 0.17, 0.21, 0.14
R_NDIFF_NWELL, R_NWELL_PDIFF, R_LVT_GATE, R_LVTN_SP = 0.34, 0.18, 0.24, 0.38
R_IMP_SP = 0.38                       # nsdm / psdm spacing: closer same-type implants are merged
CAPM11 = 1.34                         # capm to unrelated met3
VIA2_CAPM = 0.20                      # via2 clearance from a capm edge (magic capm.8)
M3_SP = 0.30


def cell_devices(design, gates, tag="u"):
    """gates: dict en/enb/pg/ng -> net names.  d = supply (outer bar), s = plate (inner bar)."""
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


class _Fet:
    """A FET PCell and the geometry the cell is packed from: x from the gate centre, y from the diffusion
    centre (the PCell is symmetric in x, so it is never mirrored)."""

    def __init__(self, dv, gate):
        from .cell import model_name
        from .pcell import fet, import_pcell
        self.comp = c = import_pcell(*fet(model_name(dv), dv.w, dv.l, gate))
        d = _ext(c, DIFF)
        self.oy = -(d[2] + d[3]) / 2                       # PCell origin -> diffusion centre

        def rel(e):
            return e and (e[0], e[1], e[2] + self.oy, e[3] + self.oy)
        self.diff, self.poly, self.lvt, self.nw = rel(d), rel(_ext(c, POLY)), rel(_ext(c, LVTN)), rel(_ext(c, NWELL))
        self.imp = rel(_ext(c, NSDM) or _ext(c, PSDM))
        li = [rel((min(p[:, 0]), max(p[:, 0]), min(p[:, 1]), max(p[:, 1]))) for p in c.get_polygons(by_spec=LI)]
        bars = [b for b in li if b[2] < self.diff[3] and b[3] > self.diff[2]]
        pad = [b for b in li if b not in bars][0]
        self.sd = max(abs(b[0] + b[1]) / 2 for b in bars)                  # bar centre from the gate
        self.bar_y = (min(b[2] for b in bars), max(b[3] for b in bars))
        self.pad, self.pad_y = pad, (pad[2] + pad[3]) / 2
        assert abs(self.diff[0] + self.diff[1]) < 1e-6, "FET PCell not symmetric in x"


class UnitCellPlan:
    """Geometry shared by every cell of an array, packed from the PCells' real layer extents and SKY130 rules.
    n_bot sample rails below the device row, n_top drive rails above it."""

    def __init__(self, design, n_bot, n_top):
        from glayout import sky130, via_stack
        from .pcell import import_pcell, mim_cap
        proto = cell_devices(design, dict(en="a", enb="b", pg="c", ng="d"), "proto")
        self.fets = f = [_Fet(d, s) for d, s in zip(proto, GATE_SIDE)]
        self.n_bot, self.n_top = n_bot, n_top
        cg = V1_M1[0] / 2 + R_M1_SP + M1_LINE / 2           # gate met1 pad centre -> supply line centre

        # x: Mdn | Msn | n-well: Msp | Mdp.  Facing inner bars carry plate met1 pads (0.27 + 0.14 apart)
        def same(a, b):
            d = max(f[a].diff[1] - f[b].diff[0] + R_DIFF_SP, f[a].sd + f[b].sd + V1_M1[0] + R_M1_SP)
            if f[b].lvt and not f[a].lvt:
                d = max(d, f[a].poly[1] - f[b].lvt[0] + R_LVT_GATE)
            if f[a].lvt and not f[b].lvt:
                d = max(d, f[a].lvt[1] + R_LVT_GATE - f[b].poly[0])
            return d

        np_d = f[1].diff[1] + R_NDIFF_NWELL - f[2].nw[0]          # n-diff to the PMOS PCell's n-well
        if f[1].lvt:
            np_d = max(np_d, f[1].lvt[1] - f[2].nw[0])           # NMOS lvtn fully outside the n-well
            if f[2].lvt:
                np_d = max(np_d, f[1].lvt[1] + R_LVTN_SP - f[2].lvt[0])
        np_d = max(np_d, 2 * cg)                                 # vin line between the two gate columns
        # NMOS edge: mirrored Mdn faces Mdn; its gate pad clears the vss line on the edge
        xg0 = max(R_DIFF_SP / 2 - f[0].diff[0], R_POLY_SP / 2 - f[0].poly[0], R_LI_SP / 2 - f[0].pad[0], cg)
        self.xg = [snap(xg0)]
        for d in (same(0, 1), np_d, same(2, 3)):
            self.xg.append(snap(self.xg[-1] + d))
        xg = self.xg
        self.x_in = [xg[0] + f[0].sd, xg[1] - f[1].sd, xg[2] + f[2].sd, xg[3] - f[3].sd]   # plate bars
        self.x_out = [xg[0] - f[0].sd, xg[1] + f[1].sd, xg[2] - f[2].sd, xg[3] + f[3].sd]  # supply bars
        self.nx0 = snap(min(xg[2] + f[2].nw[0], xg[3] + f[3].nw[0]))
        self.sup_x = {"vss": 0.0, "vin": snap((xg[1] + xg[2]) / 2), "vref": snap(xg[3] + cg)}
        w_dev = max(self.sup_x["vref"] + (V1_M1[0] + M1_LINE) / 2 + R_M1_SP,   # vdd line on the edge (room for a via pad)
                    xg[3] + f[3].diff[1] + R_DIFF_SP / 2, xg[3] + f[3].poly[1] + R_POLY_SP / 2,
                    xg[3] + f[3].pad[1] + R_LI_SP / 2)

        # MIM unit cap = SKY130 PDK PCell (C1 top contact over the capm, C2 bottom-plate strip on the right)
        side = design["cu"]["side"]
        self.unit = import_pcell(*mim_cap(side, side))
        ub = self.unit.bbox
        self.cap_x0, self.cap_x1, self.cap_y0, self.cap_y1 = ub[0][0], ub[1][0], ub[0][1], ub[1][1]
        cm = _ext(self.unit, CAPM)
        self.capm = cm
        c1 = [p for p in self.unit.get_polygons(by_spec=MET4) if min(p[:, 0]) < cm[1]][0]   # C2 is right of the capm
        self.c1_x0 = min(c1[:, 0])
        # capm.11 against the mirrored neighbour on the vss edge (capm sides face each other), met3 spacing
        # between the plates on the vdd edge (C2 sides face each other)
        self.cap_cx = snap((CAPM11 - cm[0] - self.cap_x0) / 2 + 0.0025)
        w_cap = self.cap_cx + self.cap_x1 + M3_SP / 2
        self.W = snap(max(w_dev, w_cap) + 0.0025)
        self.sup_x["vdd"] = self.W
        self.riser_x = snap(self.cap_cx + (cm[1] + self.cap_x1) / 2)     # plate via2, beside the capm
        assert self.riser_x - VIA / 2 - VIA2_CAPM >= self.cap_cx + cm[1]

        # y: rails at CTRL_PITCH; the first rail on each side clears the plate pads / via2 at the plate bus
        t_min = V1_M1[1] + R_M1_SP
        s_lim = [(-(fe.bar_y[1] - MC / 2), -(fe.bar_y[0] + MC / 2)) for fe in f]   # device shift keeping P on the bar
        tb = max([t_min] + [-fe.pad_y - s_lim[k][1] for k, fe in enumerate(f) if GATE_SIDE[k] == "bot"])
        tt = max([t_min] + [fe.pad_y + s_lim[k][0] for k, fe in enumerate(f) if GATE_SIDE[k] == "top"])
        self.shift = []
        for k, fe in enumerate(f):
            if GATE_SIDE[k] == "bot":
                self.shift.append(0.0 if -fe.pad_y <= tb else -tb - fe.pad_y)
            else:
                self.shift.append(0.0 if fe.pad_y <= tt else tt - fe.pad_y)
        h_rails = tb + tt + (n_bot + n_top - 1) * CTRL_PITCH
        h_cap = CAPM11 + max(self.cap_y1 - cm[2], cm[3] - self.cap_y0)            # capm.11 to the row above
        self.H = snap(max(h_rails, h_cap) + 0.0025)
        self.P = snap(tb + (n_bot - 0.5) * CTRL_PITCH + (self.H - h_rails) / 2)    # plate bus
        P = self.P
        self.yc = [snap(P + s) for s in self.shift]                                # diffusion centres
        self.bot_y = [snap(P - tb - (n_bot - 1 - i) * CTRL_PITCH) for i in range(n_bot)]   # bottom to top
        self.top_y = [snap(P + tt + i * CTRL_PITCH) for i in range(n_top)]
        self.ctrl_y = self.bot_y + self.top_y
        self.cap_cy = P
        self.tap = via_stack(sky130, "active_tap", "met2")
        tb_ = self.tap.bbox
        self.tap_half = max(abs(v) for v in (tb_[0][0], tb_[1][0], tb_[0][1], tb_[1][1]))
        self.ptap_y, self.ntap_y = snap(P - TAP_DY), snap(P + TAP_DY)


def draw_cell(top, plan, x0, y0, mirror, rails, gates, tag, design):
    """Draw one cell into component `top` at (x0, y0).  rails = (bottom rails, top rails), each listed bottom
    to top.  Returns reference-netlist lines for LVS."""
    from gdsfactory.components import rectangle

    from ..pdk import mos
    from .cell import model_name

    W, P, f = plan.W, plan.P, plan.fets

    def X(x):                       # local x -> layout x (mirrored about the cell centre)
        return x0 + (W - x if mirror else x)

    def rect(xa, ya, xb, yb, layer):
        xa, xb = sorted((X(xa), X(xb)))
        ya, yb = y0 + min(ya, yb), y0 + max(ya, yb)
        xa, ya, xb, yb = snap(xa), snap(ya), snap(xb), snap(yb)
        if xb - xa > 0 and yb - ya > 0:
            r = top << rectangle(size=(snap(xb - xa), snap(yb - ya)), layer=layer)
            r.move((xa, ya))

    def box(x, y, w, h, layer):
        rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, layer)

    def mcon(x, y):
        box(x, y, MC, MC, MCON)
        box(x, y, V1_M1[0] - 0.04, V1_M1[1] - 0.04, MET1)        # 0.03 / 0.06 enclosure

    def via1(x, y):                 # li -> met2: mcon, met1 pad, via1, met2 pad
        box(x, y, MC, MC, MCON)
        box(x, y, *V1_M1, MET1)
        box(x, y, V1, V1, VIA1)
        box(x, y, *V1_M2, MET2)

    devs = cell_devices(design, gates, tag)
    bot, topr = rails
    rail_y = dict(zip(bot, plan.bot_y)) | dict(zip(topr, plan.top_y))
    lines = []
    for k, (dv, fe) in enumerate(zip(devs, f)):
        xg, yc = plan.xg[k], plan.yc[k]
        ref = top << fe.comp
        ref.move((snap(X(xg)), snap(y0 + yc + fe.oy)))
        # gate: li from the PCell gate contact out to its rail, via up to the met2 rail
        side = GATE_SIDE[k]
        y_r = rail_y[dv.g]
        assert dv.g in (bot if side == "bot" else topr), f"{dv.g} is not a {side} rail"
        y_pad = yc + fe.pad_y
        rect(xg - MC / 2, min(y_pad, y_r) - MC / 2, xg + MC / 2, max(y_pad, y_r) + MC / 2, LI)
        via1(xg, y_r)
        # inner bar -> plate bus
        via1(plan.x_in[k], P)
        lines.append(mos(dv.name, dv.d, dv.g, dv.s, "vss" if dv.kind == "n" else "vdd", model_name(dv), dv.w, dv.l))
    # outer bars -> supply lines (li stubs at the plate-bus height, mcon under the met1 line)
    xo, sx = plan.x_out, plan.sup_x
    rect(sx["vss"] - MC / 2, P - MC / 2, xo[0], P + MC / 2, LI)
    rect(xo[1], P - MC / 2, xo[2], P + MC / 2, LI)
    rect(xo[3], P - MC / 2, sx["vref"] + MC / 2, P + MC / 2, LI)
    for net in ("vss", "vin", "vref"):
        mcon(sx[net], P)
    for net, x in sx.items():
        rect(x - M1_LINE / 2, 0, x + M1_LINE / 2, plan.H, MET1)
    # plate bus (met2) through the inner bars, one via2 beside the capm into the PCell plate (met3)
    xs = plan.x_in + [plan.riser_x]
    rect(min(xs) - V1_M2[0] / 2, P - V1_M2[1] / 2, max(xs) + M2_PAD / 2, P + V1_M2[1] / 2, MET2)
    box(plan.riser_x, P, M2_PAD, M2_PAD, MET2)
    box(plan.riser_x, P, VIA, VIA, VIA2)
    box(plan.riser_x, P, M3_PAD, M3_PAD, MET3)
    capref = top << plan.unit
    if mirror:                      # the PDK PCell is asymmetric (C1 left, C2 strip right): mirror it too
        capref.mirror((0, 0), (0, 1))
    capref.move((snap(X(plan.cap_cx)), snap(y0 + plan.cap_cy)))
    side = design["cu"]["side"]
    lines.append(f"XC_{tag} top p_{tag} sky130_fd_pr__cap_mim_m3_1 W={side} L={side} MF=1")
    # control rails edge to edge
    for y in plan.ctrl_y:
        rect(0, y - CTRL_W / 2, W, y + CTRL_W / 2, MET2)
    # top plate (met4 only): C1 -> stub -> vertical strap on the vss edge
    rect(-STRAP_W / 2, 0, STRAP_W / 2, plan.H, MET4)
    rect(0, plan.cap_cy - STUB_W / 2, plan.cap_cx + plan.c1_x0 + 0.2, plan.cap_cy + STUB_W / 2, MET4)
    # body taps on the cell edges, under their supply lines (shared with the mirrored neighbour)
    for tx, ty, imp in ((0.0, plan.ptap_y, PSDM), (W, plan.ntap_y, NSDM)):
        t = top << plan.tap
        t.move((snap(X(tx)), snap(y0 + ty)))
        box(tx, ty, 0.68, 0.68, imp)
    # n-well: PMOS pair + n-tap, edge to edge vertically, past the PMOS edge (merges with the neighbour's)
    rect(plan.nx0, 0, W + plan.tap_half + R_NWELL_PDIFF, plan.H, NWELL)
    # implants: bridge same-type neighbours (and the mirrored neighbours on the edges) closer than 0.38 um
    imp = [(plan.xg[k] + fe.imp[0], plan.xg[k] + fe.imp[1], plan.yc[k] + fe.imp[2], plan.yc[k] + fe.imp[3])
           for k, fe in enumerate(f)]
    for a, b, lay in ((0, 1, NSDM), (2, 3, PSDM)):
        if 0 < imp[b][0] - imp[a][1] < R_IMP_SP:
            rect(imp[a][1] - 0.01, min(imp[a][2], imp[b][2]), imp[b][0] + 0.01, max(imp[a][3], imp[b][3]), lay)
    if 2 * imp[0][0] < R_IMP_SP:
        rect(-0.05, imp[0][2], imp[0][0] + 0.01, imp[0][3], NSDM)
    if 2 * (W - imp[3][1]) < R_IMP_SP:
        rect(imp[3][1] - 0.01, imp[3][2], W + 0.05, imp[3][3], PSDM)
    return lines


def _pin(top, net, x, y, layer, size=(0.3, 0.16)):
    """Pin shape + label centred at (x, y)."""
    from gdsfactory.components import rectangle
    lbl, pin = (dict(LBL) | {MET1: (68, 5)})[layer], (dict(PIN) | {MET1: (68, 16)})[layer]
    r = top << rectangle(size=size, layer=pin)
    r.move((snap(x - size[0] / 2), snap(y - size[1] / 2)))
    top.add_label(text=net, position=(snap(x), snap(y)), layer=lbl)


def _subckt(name, pins, lines):
    return "\n".join([f".subckt {name} {' '.join(pins)}"] + lines + [f".ends {name}"]) + "\n"


def build_unit_cell(design, rails, gates, name="cdac_unit"):
    """A single unit cell (flattened), its reference netlist and pins.  rails = (bottom, top) rail names."""
    from gdsfactory import Component
    plan = UnitCellPlan(design, len(rails[0]), len(rails[1]))
    top = Component(name + "_hier")
    lines = draw_cell(top, plan, 0.0, 0.0, False, rails, gates, "u", design)
    for net, y in zip(rails[0] + rails[1], plan.ctrl_y):
        _pin(top, net, 0.3, y, MET2, (0.3, CTRL_W))
    for net, x in plan.sup_x.items():
        _pin(top, net, x, plan.H - 0.3, MET1, (0.14, 0.3))
    _pin(top, "top", 0.0, plan.H - 0.3, MET4)
    top = top.flatten()
    top.name = name
    pins = ["top"] + SUPPLY + rails[0] + rails[1]
    return top, plan, _subckt(name, pins, lines)


def build_abut_test(design, rails, gate_maps, cols=3, rows=2, name="cdac_unit_2x3"):
    """rows x cols abutted cells (mirrored alternate columns) to prove the cell tiles DRC/LVS-clean.

    Every row gets its own control-rail names; supply lines are tied below the array by met2 bars and the
    top-plate straps above it by a met4 bar, so the whole block is one LVS-checkable circuit."""
    from gdsfactory import Component
    from gdsfactory.components import rectangle
    plan = UnitCellPlan(design, len(rails[0]), len(rails[1]))
    W, H = plan.W, plan.H
    top = Component(name + "_hier")

    def rect(xa, ya, xb, yb, layer):
        r = top << rectangle(size=(snap(xb - xa), snap(yb - ya)), layer=layer)
        r.move((snap(xa), snap(ya)))

    lines, all_rails = [], []
    k = 0
    for r in range(rows):
        ren = (lambda n: n) if rows == 1 else (lambda n, r=r: f"{n}_r{r}")
        row_rails = ([ren(n) for n in rails[0]], [ren(n) for n in rails[1]])
        all_rails += row_rails[0] + row_rails[1]
        for c in range(cols):
            g = {key: ren(v) for key, v in gate_maps[k % len(gate_maps)].items()}
            lines += draw_cell(top, plan, c * W, r * H, c % 2 == 1, row_rails, g, f"{r}_{c}", design)
            k += 1
        for net, y in zip(row_rails[0] + row_rails[1], plan.ctrl_y):
            _pin(top, net, 0.3, r * H + y, MET2, (0.3, CTRL_W))
    # supply lines -> met2 bars below the array
    for i, net in enumerate(SUPPLY):
        yb = -0.5 - i * 0.45
        xs = sorted({snap(c * W + (W - plan.sup_x[net] if c % 2 else plan.sup_x[net])) for c in range(cols)})
        for x in xs:
            rect(x - M1_LINE / 2, yb - V1_M1[1] / 2, x + M1_LINE / 2, 0, MET1)
            rect(x - V1_M1[0] / 2, yb - V1_M1[1] / 2, x + V1_M1[0] / 2, yb + V1_M1[1] / 2, MET1)
            rect(x - V1 / 2, yb - V1 / 2, x + V1 / 2, yb + V1 / 2, VIA1)
        rect(xs[0] - V1_M2[0] / 2, yb - V1_M2[1] / 2, xs[-1] + V1_M2[0] / 2, yb + V1_M2[1] / 2, MET2)
        _pin(top, net, xs[0], yb, MET2, (0.3, 0.16))
    # top-plate straps -> met4 bar above the array
    xs = sorted({snap(c * W + (W if c % 2 else 0)) for c in range(cols)})
    yt = rows * H + 0.5
    for x in xs:
        rect(x - STRAP_W / 2, rows * H, x + STRAP_W / 2, yt + STRAP_W, MET4)
    rect(xs[0] - STRAP_W / 2, yt, xs[-1] + STRAP_W / 2, yt + STRAP_W, MET4)
    _pin(top, "top", xs[0], yt + STRAP_W / 2, MET4)
    top = top.flatten()
    top.name = name
    pins = ["top"] + SUPPLY + all_rails
    return top, plan, _subckt(name, pins, lines)


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
