# Layout workflow: findings

What we learned building SARGen's layout generators in SKY130: the decisions that worked, the PDK rules
that shaped the floorplans, the tool behaviour that cost time, and the numbers that justify each step.
Everything below was checked with KLayout DRC (`sky130A_mr.drc` plus our capm.10 deck), Magic DRC,
Netgen LVS and Magic parasitic extraction, and the analog blocks with post-layout transistor-level ADC
simulation in ngspice.

## 1. Results in one table

| Block | First generator | Current generator | Change | Verification |
|---|---|---|---|---|
| CDAC unit cell (2x2 um MIM + own 4 switches) | 98.1 um² (PCell cap beside gLayout FETs) | 17.5 um² (4.88 x 3.58 um) | -82 % | DRC 0 / 0, LVS match, capm.10 clean |
| 4-bit CDAC, per-unit switches | 2575 um² (54.1 x 47.6 um) | 460 um² (26.9 x 17.1 um) | -82 % | DRC 0 / 0, LVS 80 devices |
| 8-bit CDAC | 8294 um² (2.7 um cap, 12 rails / row) | 5373 um² (89.4 x 60.1 um, same cell as 4-bit) | -35 % | DRC 0 / 0, LVS 1280 devices |
| StrongARM comparator | 1671 um² (50.8 x 32.9 um) | 73 um² (8.27 x 8.79 um) with dummies and guard rings | -96 % | DRC 0 / 0, LVS match |

Post-layout 4-bit ADC (extracted CDAC + extracted comparator, transistor level): ENOB 3.97, max DNL
0.037 LSB, max INL 0.033 LSB, 18.5 uW at 10 MS/s. The schematic gives ENOB 3.96, DNL 0.063 LSB.

## 2. Methodology that worked

1. **Build one block at a time and stop for review.** Each generator (unit cell, array, comparator) was
   closed at DRC 0 / LVS match before the next one started. Composing unverified blocks hides errors.
2. **Use the PDK's own PCells for devices** (`magic::gencell sky130::...`: MIM cap and FETs), and write only
   placement and routing ourselves. PCells are correct by construction. Compared with gLayout's FET
   wrappers they are far smaller: an nfet 0.45/0.15 is 0.98 x 1.04 um against 1.72 x 2.82 um.
3. **Pack from real layer extents and rules, not bounding boxes.** Each generator reads the diffusion,
   poly, li, implant and gate-pad extents from the PCell, then places devices at the rule-limited pitch:
   diffusion 0.27, li 0.17, poly 0.21, n-diff to n-well 0.34, n-well over p-diff 0.18.
4. **Route over the devices.**
   - Horizontal met2 tracks run over the diffusion.
   - S/D bars reach their track through a via stack placed at the track's height.
   - Gate contacts reach the channel tracks by li stubs.
   - Vertical links between rows use met1, or met3 where met1 is crowded.
5. **Abutment-ready cells.**
   - Rails and supply lines run edge to edge; mirrored neighbours share edge features (vss line, taps,
     straps).
   - Every cell is geometrically identical, and only the gate via positions differ. Abutment tests
     (1x2, 2x3) prove both mirrored edges and the row edge.
6. **Measure, then optimise, on extracted layouts.** A small script reads the Magic parasitic netlist and
   reports coupling into the top plate, per-bit weight errors, and the balance of matched node pairs. Every
   layout change was judged by these numbers.

## 3. SKY130 rules that shaped the floorplans

| Rule | What it says | Consequence |
|---|---|---|
| **capm.10** | capm must not straddle nwell, diff, tap, poly, li1 or met1 | Nothing but met2 rails under a MIM cap; switches moved into the capm.11 gaps. **Not checked by `sky130A_mr.drc` or Magic**: we added `sargen/layout/capm10.drc` (legacy-deck reading). |
| capm.11 | capm >= 1.34 um from unrelated met3 | Sets the CDAC cell to 4.88 x 3.54 um minimum for a 2 x 2 um cap; mirrored columns put capm sides face to face |
| capm.8 (Magic) | no via2 under or near capm | Bottom-plate via2 sits beside the capm, in the PCell's capm-free plate extension |
| m3.3d | 0.4 um spacing to met3 wider than 3 um in **both** directions | The 2.7 um cap plates (8-bit sizing) need 0.4 um between plates; 2 um caps do not |
| MIM PCell minimum | `wmin = lmin = 2.0` um; smaller requests are clamped | The unit cap of every resolution is 2 x 2 um, ~9.3 fF (model: 2.0 fF/um² + 0.19 fF/um, -0.025 um edge bias) |
| lvtn | must not straddle the n-well; enclose gates by 0.18; 0.24 to SVT gates; 0.38 spacing | LVT NMOS kept fully outside the PMOS well; LVT/SVT neighbours spaced |
| nsdm / psdm | 0.38 width and spacing | Same-type implants of neighbours merged; one implant rectangle per device region avoids slivers |
| poly.2 next to gate pads | 0.21 um | Two fingers sharing a contact bar at 0.44 um pitch cannot have gate contacts on opposite sides (0.20 um): such pairs get a split contact (two bars, +0.34 um) |
| mcon spacing | 0.19 um (licon 0.17) | Tap contacts on a 0.36 um pitch |
| met5 | TinyTapeout power grid | No met5 or via4 anywhere; top plates on met4 |

## 4. Tool behaviour that cost time

- **gdsfactory `rectangle()` rounds sizes to two grid steps** (10 nm when no PDK is active). Shapes with an
  odd 5 nm width grow by 5 nm, which caused slivers at column abutments, an n-well 5 nm under a cap, and a
  riser 2 nm too close to a cap. All generators now draw exact polygons (`_poly`).
- **Magic types devices per cell.** Diffusion, poly and implants (lvtn) must be in the same cell, so
  generated blocks are flattened before DRC and extraction.
- **PCell text labels become nets.** Magic PCells carry `D`, `S`, `G`, `C1`, `C2` labels, which shorted
  every device of an array in LVS. They are stripped on import.
- **The MIM PCell's bottom-plate contact strip (C2) cannot be removed** (`bconnect 0` keeps it). The top
  plate is routed around it.
- **Cell pitches on a 0.01 um grid.** With a 5 nm-odd cell width, multiples and halves land off the 5 nm
  grid at abutments, so cell widths and heights are rounded up to 0.01 um.
- **Geometry that only appears when tiling.** A single cell can be clean while the array fails: shared
  edges, rows meeting, and bars added above the array. Every cell change is re-verified as a 1x2, a 2x3
  and the full array.
- gLayout names metals from li upward (its `met1` is SKY130 li), and needs a pinned environment:
  gdsfactory 7.7, numpy 1.26, `PYTHONPATH` unset.

## 5. Design decisions with their evidence

**CDAC**
- **Per-unit switches + common-centroid row-wise grid.**
  - Every bit is built from point-symmetric pairs, so its centroid sits exactly at the array centre.
  - The packer allows at most 3 bits per row, so every resolution from 3 to 8 bits fits the same 8-track
    cell.
- **Top plate:** C1 contact, then a short met4 stub, then a vertical met4 strap on the vss edge. The
  plates are joined by a met4 bar **below** the array. Above the array, the bar added 0.2 fF of fringe to
  the top-row (MSB) units only.
- **Extracted coupling into the top plate:**
  - Control rails: 0.92 fF in total (0.6 % of C_total).
  - vin: 0.34 fF.
  - Systematic bit-weight error: < 0.04 % (0.0003 LSB).
- **Noise budget at 4 bits:**
  - kT/C: about 158 uV rms.
  - Quantization: 32.5 mV rms.
  - So the unit cap is set by the PCell minimum, not by noise. Coupling into the *bottom* plates is
    harmless, because they are driven nodes. The top plate is the sensitive node.
- **Trade-off:** fixing the unit cap at 2 x 2 um for 8 bits gives a predicted 3-sigma mid-code DNL of
  ~0.67 LSB, against the 0.5 LSB target. This uses the PDK matching coefficient 2.8 %·um, which is
  probably pessimistic. Still to settle: keep the cap at 2 um and accept that DNL, or let the 8-bit sizing
  choose a larger cap.

**StrongARM comparator** (Razavi SSC Mag. 2015/2020; Hastings; Boser EE240B; Sharma et al. DATE 2021)
- Mirror symmetry about one axis, with the tail and clock on the axis.
- Clustered input pair `dmy tail A xp A tail B xn B tail dmy`. Each drain is an identical inner diffusion,
  so xp and xn carry equal capacitance. At this size, clustering beats common-centroid (Sharma).
- Standard-Vt devices everywhere: SKY130 LVT matches ~1.6x worse.
- Latch and reset PMOS share diffusion. The output inverters are columns under their PMOS.
- outp/outn tracks swap on the axis, plus a met3 trim stub tuned on extraction.

  | Extracted node pair | Balance |
  |---|---|
  | outp / outn | 4.1 % -> 0.04 % (after the trim stub) |
  | xp / xn | 0.03 – 0.4 % |
  | inp / inn | 0.05 % |

- Dummy fingers at both ends of the input pair.
- p-tap and n-tap guard stripes that, with the rail taps, ring the NMOS and the PMOS.

## 6. Open items

- **Leakage on the floating top plate.** The schematic PVT sweep degrades only at hot fast-NMOS corners:
  fs / 125 C gives DNL 0.24, INL 0.28, offset -0.40 LSB, and power doubles. The suspected cause is leakage
  through the LVT switches; a standard-Vt top-plate switch is the candidate fix.
- **CDAC dummy ring** for etch/edge effects. Extraction does not model these. The proposed rule is to add
  the ring for 6 bits and up: about +27 % area at 8 bits, against +94 % at 4 bits.
- **8-bit comparator.** Its latch devices (16.6 um) need multi-finger support in the comparator generator.
- **Remaining blocks:** SAR logic layout, top-level assembly, TinyTapeout pins.
- **Post-layout PVT + Monte Carlo** of the full core.

## 7. References

- B. Razavi, "The StrongARM Latch," IEEE SSC Magazine, 2015;
  "The Design of a Comparator," IEEE SSC Magazine, 2020.
- A. Hastings, *The Art of Analog Layout*, 2nd ed., Prentice Hall.
- B. Boser, Berkeley EE240B lecture "Layout" (matching, dummies, symmetric wiring).
- M. Pelgrom et al., "Matching properties of MOS transistors," IEEE JSSC, 1989.
- Sharma et al., common-centroid vs clustered layouts of small StrongARM latches, DATE 2021.
- B. Murmann, "Thermal Noise in Track-and-Hold Circuits," IEEE SSC Magazine, 2012.
- C.-C. Liu et al., 10-bit 50-MS/s SAR ADC with monotonic switching, IEEE JSSC, 2010.
- SkyWater SKY130 periphery rules (capm.*, m3.*, lvtn.*):
  https://skywater-pdk.readthedocs.io/en/main/rules/periphery.html
- SkyWater SKY130 RCX notes (MIM coupling to underlying routing not extracted):
  https://skywater-pdk.readthedocs.io/en/main/rules/rcx.html
