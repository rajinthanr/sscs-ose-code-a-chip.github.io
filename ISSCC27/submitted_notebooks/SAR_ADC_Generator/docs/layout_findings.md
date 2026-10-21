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
| 4-bit CDAC, per-unit switches | 2575 um² (54.1 x 47.6 um) | 460 um² (26.9 x 17.1 um); 875 um² (36.0 x 24.3 um) with the dummy-cap ring | -82 % / -66 % | DRC 0 / 0, LVS 80 devices + ring |
| 8-bit CDAC | 8294 um² (2.7 um cap, 12 rails / row) | 5373 um² (89.4 x 60.1 um, same cell as 4-bit); 6626 um² with the dummy-cap ring | -35 % / -20 % | DRC 0 / 0, LVS 1280 devices + ring |
| StrongARM comparator (one generator, 4-8 bit) | 1671 um² (50.8 x 32.9 um, 4-bit) | 73 um² device area (8.27 x 8.79 um) with dummies and guard rings; with pin exits 9.87 x 8.79 um (4-bit), 11.43 x 8.99 um (6-bit), 32.6 x 12.5 um (8-bit) | -96 % (4-bit) | DRC 0 / 0, LVS match at 4, 6 and 8 bits |
| Top-plate switch (TG in closed guard rings) | - | 4.45 x 5.77 um (4-bit), 6.37 x 7.52 um (6-bit), 25.6 x 8.4 um (8-bit) | - | DRC 0 / 0, LVS match |
| SAR logic (LibreLane, sky130_fd_sc_hd) | - | 548 um² (4-bit), 801 um² (6-bit), 1122 um² (8-bit) | - | DRC 0 / 0, LVS match (incl. decaps) |
| Routed core (CDAC + comparator + top switch + logic) | - | 65.4 x 41.8 um (4-bit), 94.2 x 57.3 um (6-bit), 142.9 x 88.9 um (8-bit) | - | DRC 0 / 0, LVS match at 4, 6 and 8 bits |

Post-layout 4-bit ADC (extracted CDAC + extracted comparator, transistor level): ENOB 3.97, max DNL
0.037 LSB, max INL 0.033 LSB, 18.5 uW at 10 MS/s. The schematic gives ENOB 3.96, DNL 0.063 LSB.
Full routed 4-bit core extracted flat (CDAC, comparator, top switch and SAR logic with all routing):
ENOB 3.98, max DNL 0.037 LSB, max INL 0.024 LSB, offset -0.09 LSB, gain -0.02 LSB, 25.4 uW.

Reproduce (gLayout venv, see `README.md`): `python run_layout.py <block> --bits N [--pex]` for cdacu,
comparator, topsw, sarlogic, then core; `python collect_layout.py N`; `python run_postlayout.py --bits N`;
`python studies/postlayout_pvt.py --bits N` for the extracted core across PVT.

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

- **Leakage on the floating top plate.** Diagnosed (section 6c): the top-plate switch's LVT PMOS leaks at
  fs / ff 125 C, and a standard-Vt PMOS does not settle at ss / -40 C. Decision (2026-10-21): keep the sized
  LVT switch; the extracted 4-bit core stays within DNL 0.13 LSB at every corner. Options for a later
  revision: a wider standard-Vt or longer-L LVT PMOS, or a bootstrapped switch.
- **8-bit post-layout.** The 8-bit core is assembled and clean (section 6d); its extracted transistor-level
  simulation is the remaining check.
- **Remaining blocks:** TinyTapeout tile integration (pins, analog ground, Vref decoupling).
- **Post-layout PVT + Monte Carlo** of the full core.

## 6a. Dummies and guard rings per block

Hard SKY130 rules are only latch-up: LU.2 / LU.3 (every n-diffusion within 15 um of a contacted p-tap, every
p-diffusion within 15 um of an n-tap; Magic `sky130A.tech`) and nwell.4 (every n-well has a contacted tap).
Everything else is practice, worth its area only where an error budget needs it (1 LSB = 112 mV at 4 bits,
7 mV at 8 bits).

| Block | Dummies | Guard ring | Priority | SARGen now |
|---|---|---|---|---|
| CDAC MIM array | ring of grounded dummy unit caps (edge etch / density) | none (metal stack) | optional at 4 bits, should at 8 bits | done for every resolution: one ring at unit-cell pitch (mirrored like the real columns), plates shorted on met4 and tied to vss by a met3 ring (+90 % area at 4 bits, +23 % at 8 bits) |
| CDAC per-unit switches | none (no ratio matching) | no ring; taps within 15 um | taps must | p-taps / n-taps on the cell edges, shared |
| Top-plate sampling switch | optional half-size charge-injection dummies (circuit) | p+ ring to a quiet ground (its diffusion is the floating top plate's only junction) | should | not laid out yet |
| Comparator input pair | end dummies | p+ ring with the tail | must / should | done: dummy fingers + p-tap ring |
| Comparator latch NMOS | end dummies (mismatch / 4 at the input) | same p+ ring | should | done: outer dummy finger per side (gate on the latch gate net, diffusions on the output node), no extra area |
| Comparator latch / reset PMOS | optional (mismatch / 10) | n+ ring | n-tap must, ring should | n-tap ring done |
| Output inverters | balance the loads on qp / qn | taps | should | symmetric, equal loads |
| SAR logic (hd cells) | none | none; tap cells every 13 um (`FP_TAPCELL_DIST`), decaps, a p+ strip toward the comparator | taps must | not laid out yet |
| Vref / clock lines | grounded shield tracks between clock and the top plate / comparator P, Q nodes | n/a | should | comparator clock tracks sit at the cell's top and bottom edges, two device rows from xp / xn and the outputs, so there is no parallel run to shield; extracted clk coupling xp / xn 50.4 / 50.8 aF, inp / inn 110.9 / 110.9 aF, outp / outn 171 / 164 aF |

TinyTapeout: met5 forbidden; the analog pin path is < 500 ohm and < 5 pF; ~20 mA gives ~0.1 V drop through
the power grid, so decouple vref on chip and give the analog ground its own branch from VGND. Substrate
noise from neighbouring tiles: distance first (comparator and top-plate switch at the tile edge away from the
SAR logic), then p+ rings. Deep n-well costs >= 6 um per side (dnwell / nwell.5 / nwell.7) and is only worth
considering for an 8-bit comparator. Sources: Razavi, SSC Magazine 2015; Pelgrom, JSSC 1989; Hastings;
WVU EE551 analog layout notes; SkyWater periphery rules; tinytapeout.com/specs/analog; open_pdks guard-ring
generators.

## 6b. ALIGN as an alternative layout engine

ALIGN (ALIGN-public + ALIGN-pdk-sky130) was tried twice for the StrongARM, always with a container memory
cap on this 15 GB host.
- Flat netlist (2026-10-20): killed at the 6 GB cap during placement. It also ignores L (fixed 0.15 um,
  long channels only as stacks) and needs W on a 0.21 um grid.
- Hierarchical netlist (2026-10-21; input stage, cross-coupled NMOS, PMOS latch, reset, inverters):
  - any `SymmetricBlocks` constraint made placement explode past 5 GB, even for a two-transistor block;
  - without symmetry constraints every sub-block places, but memory grows from block to block and the full
    comparator was killed at 6.7 GB before routing.

So ALIGN produced no comparator on this machine, and placing it without symmetry constraints would defeat
the purpose anyway. The custom generator gives a DRC/LVS-clean, symmetric 73 um^2 comparator in about 2 s.

## 6c. Top-plate switch, SAR logic and core

- **Top-plate switch** (`topswitch.py`): a transmission gate in closed guard rings, a p+ ring to vss around the
  NMOS and an n-tap ring to vdd around the PMOS.
  - The switch is the floating top plate's only junction to the substrate.
  - Fingers keep the top node on inner shared bars.
  - 4-bit: 4.45 x 5.62 um including its pin exits.
- **Leakage at hot, fast-NMOS corners** (schematic, fixed 4-bit design, fs / 125 C):

  | Top-plate switch | DNL | INL | Offset | Gain |
  |---|---|---|---|---|
  | LVT (as designed) | 0.26 | 0.29 | -0.40 | +0.28 |
  | Standard-Vt | 0.07 | 0.06 | -0.14 | +0.01 |
  | Standard-Vt unit switches instead (top switch stays LVT) | 0.33 | 0.30 | -0.40 | +0.34 |

  - The top-plate switch's LVT leakage during conversion is the cause. The unit switches' leakage only costs power.
  - A standard-Vt top switch fails to settle at ss / -40 C (ENOB 3.19), which is why sizing picked LVT.
  - Both mixed gates were checked at every corner (full table: `results/4bit/sweeps/top_switch_leakage.md`,
    rerun with `studies/top_switch_leakage.py`):

    | Top-plate switch | fs / 125 C DNL | ff / 125 C DNL | ss / -40 C 1.80 V ENOB | ss / -40 C 1.62 V ENOB |
    |---|---|---|---|---|
    | LVT N + LVT P (sized) | 0.26 | 0.20 | 3.98 | - |
    | SVT N + SVT P | 0.07 | 0.07 | 3.19 | 2.99 |
    | SVT N + LVT P | 0.33 | 0.20 | 3.99 | 3.74 |
    | LVT N + SVT P | 0.07 | 0.07 | 3.60 | 3.29 |

  - Reading: the leak is through the PMOS (the top plate sits near vcm, and the LVT PMOS leaks most when hot);
    the cold-corner settling is carried by the PMOS too. One device does both jobs, so no threshold choice wins
    every corner at this size.
  - Fixes still open, each consistent with the sizing rules: a wider standard-Vt PMOS (settling scales with W,
    subthreshold leakage too, but from a far lower base), a longer-L LVT PMOS (leakage falls faster than
    on-conductance), or a bootstrapped top switch. This is a sizing decision for the generator's switch step,
    not a layout one; the layout generator already takes any flavour.
- **SAR logic** (`sarlogic.py`): LibreLane 3.1 Classic hardens the same standard cells as the SPICE netlist.
  - No resizing, port buffers or clock tree, so the drive strengths stay as sized for 2^i units.
  - Routing up to met4, met4-only power grid, tap cells and decaps.
  - Pins placed by side toward what they connect to.
  - 23.4 x 23.4 um, clean under LibreLane's checks and under our own (the LVS reference includes the decaps).
- **Core** (`core.py`): blocks placed from their pin labels and routed by script.
  - The top-plate net is met4 only.
  - pg/ng reach the CDAC trunks through a met3/met2 channel at spots clear of the rails.
  - Signal buses are met3; power buses are met4 (vss) and met3 (vdd).
  - Result: 65.4 x 42.1 um, DRC 0/0, LVS match.
  - Shorts caught by LVS and fixed:
    - the CDAC's vss and vdd drops on the same x;
    - the top switch's power drops crossing the top-plate stub;
    - vdd's met3 hop landing on a phase bus.
  - Lesson: route power away from the top-plate net by construction, and run LVS on every assembly change.
- **Extracted core across PVT** (4-bit, 17 points, the schematic sweep's corners, `studies/postlayout_pvt.py`):

  | 17 PVT points | min ENOB | max DNL | max INL | max abs offset | power |
  |---|---|---|---|---|---|
  | schematic | 3.95 | 0.262 | 0.285 | 0.40 | 11.2 - 31.1 uW |
  | extracted routed core | 3.95 | 0.129 | 0.123 | 0.21 | 20.4 - 45.0 uW |

  - The hot-corner leakage still shows (fs / 125 C: DNL 0.13, offset -0.21 LSB, 45 uW) but at about half the
    schematic's size. Likely reason (not separately tested): the ~20 fF of extracted wiring on the top plate
    adds to its capacitance, so the same leakage current moves it less.
  - DNL is resolved in steps of 1/16 LSB at 16 hits per code: 0.004 and 0.070 differ by one step.
- **Post-layout power.** Linearity holds in the extracted cores, but power rises: 4-bit 13.9 -> 25.4 uW,
  6-bit 33.8 -> 63.1 uW (ENOB 6.02, DNL 0.048 LSB, INL 0.067 LSB). Supply charge per 4-bit ramp, by
  extraction step:

  | Case | vdd | vref |
  |---|---|---|
  | schematic | 307 | 91 |
  | extracted unit-cell CDAC | 372 | 130 |
  | + extracted comparator | 417 | 130 |
  | full routed core | 594 | 132 |

  - vref: the whole increase (+43 %) comes from the CDAC array, i.e. bottom-plate and control-rail parasitics
    that the reference charges each cycle.
  - vdd: most of it comes from wiring the logic drives at core level: the per-bit switch-control lines
    pg/ng (about 93 fF in total, 9-14 fF per line) and the comparator clock bus (12 fF).
  - So the schematic power estimate needs a wiring term proportional to the array size before the FoM is
    quoted, and shorter control lines (logic closer to the array, or per-row drivers) are the lever.

## 6d. One comparator generator for 4 to 8 bits

The sizing (`design['cmp']`) sets the device widths; `strongarm.py` turns them into fingers and placement with
the same topology at every resolution, so the 8-bit comparator needs no separate architecture:

| Rule | 4-bit | 6-bit | 8-bit |
|---|---|---|---|
| input pair: even fingers per device, each <= 2.5 um, clustered and mirrored (`A...A \| B...B`) | 2 x 1.0 um | 2 x 1.05 um | 14 x 2.36 um |
| tail: as many fingers as the pair, tail node on the axis | 4 x 0.75 um | 4 x 0.8 um | 28 x 1.78 um |
| latch NMOS / PMOS: odd finger counts <= 2 um (bars keep their places) | 1 | 1 | 9 x 1.84 um |
| output trim stub: 0.80 um + 0.05 um per extra latch finger | 0.80 um | 0.80 um | 1.20 um |
| size with pin exits | 9.87 x 8.79 um | 11.43 x 8.99 um | 32.6 x 12.5 um |

- Routing scales with the bar counts: a met2 tail track over each row joined on the axis; one via per
  input-comb segment; met2 band tracks for multi-bar xp / xn (left / right at one height) with a met3 link to
  the latch when bars do not line up; drain vias clustered in the output channel.
- **Common centroid was tried for the 8-bit pair and dropped.** An `ABBA` pattern (16 fingers per device)
  was DRC/LVS clean, but extraction showed xp / xn 1.1 % apart and their coupling to the inputs unbalanced
  (xn-inp 0.49 fF vs xp-inn 0.13 fF: the band tracks run parallel to different input tracks). The pattern is
  common-centroid but not mirror-symmetric, so every connection differs between the sides. Clustered and
  mirrored restores exact images, in line with Sharma et al. (DATE 2021); the gradient term common centroid
  would cancel is small over the pair's ~16 um next to the random mismatch the sizing allows (Pelgrom).
- Extracted balance with the final generator:

  | Comparator | outp / outn | xp / xn |
  |---|---|---|
  | 4-bit | 0.28 % | 0.44 % |
  | 6-bit | 0.15 % | 0.42 % |
  | 8-bit | 0.07 % | 0.24 % |

- **Top-plate switch at 8 bits** (17 NMOS + 34 PMOS fingers): two tracks let an NMOS drop to the far track pass
  a PMOS drop of the other net at the same x. Three tracks fix it for any finger count: NMOS vcm, shared top,
  PMOS vcm (0.46 um apart so via pads of drops at one x stay clear), the two vcm tracks joined on met3.

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
