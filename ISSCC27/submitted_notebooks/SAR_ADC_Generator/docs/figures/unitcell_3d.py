"""Exploded 3D view of the CDAC unit cell (layer polygons from export_unitcell.py) -> docs/unitcell_3d.png"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import proj3d
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

L = json.load(open("build/figures/unitcell_layers.json"))
x0, y0, x1, y1 = L["bbox"]
# (layer, height in the exploded stack, colour, label); devices at the bottom, top plate on top
STACK = [("diff", 0.0, "#1baf7a", "transistors (diffusion + poly gates)"), ("poly", 0.0, "#e34948", None),
         ("li", 1.0, "#9085e9", "local interconnect (li)"), ("met1", 2.0, "#2a78d6", "metal 1"),
         ("met2", 3.0, "#e87ba4", "metal 2: control rails"), ("met3", 4.0, "#eb6834", "metal 3: capacitor bottom plate"),
         ("capm", 4.45, "#eda100", "MIM capacitor (capm)"), ("met4", 5.4, "#6b7280", "metal 4: top plate")]
fig = plt.figure(figsize=(12.5, 9.6))
ax = fig.add_axes([0.0, 0.0, 0.74, 0.86], projection="3d")
for name, z, col, _ in STACK:
    polys = [[(x, y, z) for x, y in p] for p in L[name]]
    if polys:
        ax.add_collection3d(Poly3DCollection(polys, facecolor=col, edgecolor=col, linewidths=0.6,
                                             alpha=0.30 if name in ("met3", "capm") else 0.55))
    if name == "poly":
        continue
    # faint plane outline of the cell at this level
    ax.add_collection3d(Line3DCollection([[(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (x0, y0, z)]],
                                         colors="#c7cbd1", linewidths=0.6))
# the capacitor footprint projected down through every layer: only metal 2 may cross it (rule capm.10)
cx = [p[0] for p in L["capm"][0]]; cy = [p[1] for p in L["capm"][0]]
fx0, fx1, fy0, fy1 = min(cx), max(cx), min(cy), max(cy)
for name, z, _, _ in STACK[:6]:
    if name == "poly":
        continue
    if True:
        ax.add_collection3d(Poly3DCollection([[(fx0, fy0, z), (fx1, fy0, z), (fx1, fy1, z), (fx0, fy1, z)]],
                                             facecolor="#1d2330", edgecolor="none", alpha=0.07))
    ax.plot([fx0, fx1, fx1, fx0, fx0], [fy0, fy0, fy1, fy1, fy0], [z] * 5, color="#1d2330", lw=1.0, ls="--")
for x, y in ((fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1)):
    ax.plot([x, x], [y, y], [0, 4.45], color="#1d2330", lw=0.6, ls=":")
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_zlim(0, 5.6)
ax.set_box_aspect((x1 - x0, y1 - y0, 9.0))
ax.view_init(elev=20, azim=-62)
ax.set_axis_off()
# direct labels on the right, one per layer, at the layer's height in the figure
for name, z, col, lab in STACK:
    if lab is None:
        continue
    X, Y, _ = proj3d.proj_transform(x1, y1 * 0.5, z, ax.get_proj())
    px, py = fig.transFigure.inverted().transform(ax.transData.transform((X, Y)))
    fig.text(0.75, py, lab, fontsize=11.5, color="#1d2330", va="center",
             bbox=dict(boxstyle="round,pad=0.25", fc=col, ec="none", alpha=0.25))
fig.text(0.03, 0.955, "One CDAC unit cell, layers pulled apart", fontsize=16, fontweight="bold")
fig.text(0.03, 0.915, "The dashed, shaded square is the capacitor's footprint: under it, only metal-2 control rails may pass "
         "(SKY130 rule capm.10),\nso the switches sit beside the capacitor. The top plate stays on metal 4.",
         fontsize=11.5, color="#4b5563", va="top")
fig.text(0.03, 0.03, f"4-bit unit cell, {x1 - x0:.2f} x {y1 - y0:.2f} µm, 2 x 2 µm MIM capacitor; vertical spacing not to scale",
         fontsize=10, color="#6b7280")
fig.savefig("docs/unitcell_3d.png", dpi=100, facecolor="white")
from PIL import Image
Image.open("docs/unitcell_3d.png").convert("RGB").quantize(colors=192, dither=Image.Dither.NONE).save(
    "docs/unitcell_3d.png", optimize=True)
print("ok")
