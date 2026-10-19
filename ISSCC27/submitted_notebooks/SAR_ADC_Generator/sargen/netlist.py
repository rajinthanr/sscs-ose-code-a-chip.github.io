"""SPICE netlist generation for the SAR ADC and its building blocks (SKY130 + ngspice XSPICE).

Signal naming
-------------
top          CDAC top plate = comparator input (+)
vcm          common-mode reference = comparator input (-)
bot_<i>      bottom plate of bit-i capacitor group (i = 0 is the LSB); botd = dummy cap
phis/phisb   bottom-plate sampling phase (and complement)
phit/phitb   top-plate sampling phase; opens slightly before phis (bottom-plate sampling)
clk          comparator clock (high = evaluate)
qp           comparator output, high when top < vcm  -> bit decision "keep"
bo_<i>       analog copy of output bit i, for read-out
"""

from dataclasses import dataclass

from .pdk import MIM, NFET, PFET, lib_line, mim, mos

TR = 50e-12  # edge time of ideal timing sources


# ---------------------------------------------------------------- building blocks
def strongarm_subckt(c: dict) -> str:
    """StrongARM latch with output inverters. Ports: inp inn clk qp qn vdd vss."""
    L = c["l"]
    lines = [
        ".subckt strongarm inp inn clk qp qn vdd vss",
        mos("Mt", "tail", "clk", "vss", "vss", NFET, c["w_tail"], L),
        mos("Mi1", "xp", "inp", "tail", "vss", NFET, c["w_in"], c["l_in"]),
        mos("Mi2", "xn", "inn", "tail", "vss", NFET, c["w_in"], c["l_in"]),
        mos("Mn1", "outn", "outp", "xp", "vss", NFET, c["w_ln"], L),
        mos("Mn2", "outp", "outn", "xn", "vss", NFET, c["w_ln"], L),
        mos("Mp1", "outn", "outp", "vdd", "vdd", PFET, c["w_lp"], L),
        mos("Mp2", "outp", "outn", "vdd", "vdd", PFET, c["w_lp"], L),
        mos("Mr1", "outn", "clk", "vdd", "vdd", PFET, c["w_rst"], L),
        mos("Mr2", "outp", "clk", "vdd", "vdd", PFET, c["w_rst"], L),
        mos("Mr3", "xp", "clk", "vdd", "vdd", PFET, c["w_rst"], L),
        mos("Mr4", "xn", "clk", "vdd", "vdd", PFET, c["w_rst"], L),
        # qp = NOT(outp): outp is pulled low when inp < inn
        mos("Mon1", "qp", "outp", "vss", "vss", NFET, c["w_inv_n"], L),
        mos("Mop1", "qp", "outp", "vdd", "vdd", PFET, c["w_inv_p"], L),
        mos("Mon2", "qn", "outn", "vss", "vss", NFET, c["w_inv_n"], L),
        mos("Mop2", "qn", "outn", "vdd", "vdd", PFET, c["w_inv_p"], L),
        ".ends strongarm",
    ]
    return "\n".join(lines)


def tg_lines(name, a, b, en, enb, wn, wp, l, m=1) -> list[str]:
    return [mos(f"{name}n", a, en, b, "0", NFET, wn, l, m),
            mos(f"{name}p", a, enb, b, "vdd", PFET, wp, l, m)]


# ---------------------------------------------------------------- SAR core
def sar_core(design: dict, bits: int, cp_top: float = 0.0) -> str:
    """CDAC + switches + comparator (transistor level)."""
    cu, sw, drv, L = design["cu"], design["sw"], design["drv"], design["l_sw"]
    out = ["* ---- comparator", "Xcmp top vcm clk qp qn vdd 0 strongarm",
           "* ---- top-plate sampling switch (to vcm)"]
    out += tg_lines("Mtt", "top", "vcm", "phit", "phitb", sw["top_wn"], sw["top_wp"], L)
    for i in range(bits):
        m = 2**i
        out.append(f"* ---- bit {i}: {m} unit cap(s), binary-scaled switches")
        for u in range(m):
            out.append(mim(f"C{i}_{u}", "top", f"bot_{i}", cu["side"], cu["side"]))
        out += tg_lines(f"Ms{i}", f"bot_{i}", "vin", "phis", "phisb", sw["in_wn"], sw["in_wp"], L, m)
        out.append(mos(f"Mdp{i}", f"bot_{i}", f"pg_{i}", "vref", "vdd", PFET, drv["wp"], L, m))
        out.append(mos(f"Mdn{i}", f"bot_{i}", f"ng_{i}", "0", "0", NFET, drv["wn"], L, m))
    out.append("* ---- dummy (termination) unit cap: samples vin, then grounded")
    out.append(mim("Cd", "top", "botd", cu["side"], cu["side"]))
    out += tg_lines("Msd", "botd", "vin", "phis", "phisb", sw["in_wn"], sw["in_wp"], L)
    out.append(mos("Mddn", "botd", "phisb", "0", "0", NFET, drv["wn"], L))
    if cp_top > 0:
        out.append(f"Cptop top 0 {cp_top:.4g}")
    return "\n".join(out)


def sar_logic(bits: int, vdd: float) -> str:
    """Synchronous SAR logic in XSPICE digital models (idealised, zero power)."""
    dig_in = ["phis", "clkt", "en"] + [f"trial_{i}" for i in range(bits)] + \
             [f"latch_{i}" for i in range(bits)] + ["qp"]
    ana_in = " ".join(dig_in)
    dig = " ".join(f"d_{n}" for n in dig_in)
    lines = [
        "* ---- SAR logic (XSPICE)",
        f"abr_in [{ana_in}] [{dig}] adc_b",
        "aphisb d_phis d_phisb inv_d",
        "aclk [d_clkt d_en] d_clk and_d",
    ]
    outs_d, outs_a = ["d_clk"], ["clk"]
    for i in range(bits):
        lines += [
            f"aff{i} d_qp d_latch_{i} NULL d_phis d_b{i} d_b{i}n dff_d",
            f"aor{i} [d_trial_{i} d_b{i}] d_ctrl{i} or_d",
            f"apg{i} [d_ctrl{i} d_phisb] d_pg{i} nand_d",
            f"ang{i} [d_ctrl{i} d_phis] d_ng{i} nor_d",
        ]
        outs_d += [f"d_pg{i}", f"d_ng{i}", f"d_b{i}"]
        outs_a += [f"pg_{i}", f"ng_{i}", f"bo_{i}"]
    lines += [
        f"abr_out [{' '.join(outs_d)}] [{' '.join(outs_a)}] dac_b",
        ".model adc_b adc_bridge(in_low=0.7 in_high=1.1 rise_delay=1e-11 fall_delay=1e-11)",
        f".model dac_b dac_bridge(out_low=0 out_high={vdd} out_undef={vdd / 2} t_rise={TR} t_fall={TR})",
        ".model inv_d d_inverter(rise_delay=2e-11 fall_delay=2e-11)",
        ".model and_d d_and(rise_delay=2e-11 fall_delay=2e-11)",
        ".model or_d d_or(rise_delay=2e-11 fall_delay=2e-11)",
        ".model nand_d d_nand(rise_delay=2e-11 fall_delay=2e-11)",
        ".model nor_d d_nor(rise_delay=2e-11 fall_delay=2e-11)",
        ".model dff_d d_dff(clk_delay=3e-11 reset_delay=3e-11 rise_delay=2e-11 fall_delay=2e-11)",
    ]
    return "\n".join(lines)


@dataclass
class Timing:
    """Phase plan of one conversion (all times relative to the conversion start)."""
    bits: int
    tclk: float

    @property
    def tconv(self):
        return (self.bits + 2) * self.tclk

    @property
    def t_top_open(self):          # sampling instant (top plate opens first)
        return 0.85 * self.tclk

    @property
    def t_bot_open(self):
        return 0.90 * self.tclk

    @property
    def t_read(self):              # all bits final, read-out instant
        return (self.bits + 1.5) * self.tclk

    def sources(self, vdd: float) -> str:
        T, Tc, N = self.tclk, self.tconv, self.bits
        p = lambda name, td, pw, per, inv=False: (  # noqa: E731
            f"V{name} {name} 0 PULSE({vdd if inv else 0} {0 if inv else vdd} "
            f"{td:.6g} {TR} {TR} {pw - TR:.6g} {per:.6g})")
        lines = ["* ---- timing (ideal sources)",
                 p("phis", 0, self.t_bot_open, Tc), p("phisb", 0, self.t_bot_open, Tc, True),
                 p("phit", 0, self.t_top_open, Tc), p("phitb", 0, self.t_top_open, Tc, True),
                 p("clkt", 0.5 * T, 0.45 * T, T),          # comparator clock template
                 p("en", T, N * T, Tc)]                    # enable during bit trials
        for i in range(N):
            k = N - i                                      # bit i is tried in cycle k (MSB first)
            if i == N - 1:
                # MSB is set the moment sampling ends, so the top plate stays within
                # [Vcm - Vref/2, Vcm + Vref/2] and never forward-biases the switch junctions
                lines.append(p(f"trial_{i}", self.t_bot_open, 2 * T - self.t_bot_open, Tc))
            else:
                lines.append(p(f"trial_{i}", k * T, T, Tc))
            lines.append(p(f"latch_{i}", k * T + 0.93 * T, 0.04 * T, Tc))
        return "\n".join(lines)


def sar_testbench(spec, design: dict, vin_line: str, n_conv: int, *, mismatch=False,
                  cp_top=0.0, save=None, power=True) -> str:
    """Full transient testbench with `n_conv` conversions (+1 leading dummy conversion)."""
    tim = Timing(spec.bits, spec.tclk)
    tstop = (n_conv + 1) * tim.tconv
    save = save or [f"v(bo_{i})" for i in range(spec.bits)]
    meas = ""
    if power:
        t0 = tim.tconv
        meas = (f"meas tran q_vdd integ i(vdd) from={t0:.6g} to={tstop:.6g}\n"
                f"meas tran q_vref integ i(vref) from={t0:.6g} to={tstop:.6g}\n"
                f"meas tran q_vcm integ i(vcm) from={t0:.6g} to={tstop:.6g}\n"
                "print q_vdd q_vref q_vcm > power.txt\n")
    return f"""* SAR ADC {spec.bits}-bit testbench (generated by sargen)
{lib_line(spec.corner, mismatch)}
.temp {spec.temp}
.option method=gear
{strongarm_subckt(design['cmp'])}
Vdd vdd 0 {spec.vdd}
Vref vref 0 {spec.vref}
Vcm vcm 0 {spec.vcm}
{vin_line}
{tim.sources(spec.vdd)}
{sar_core(design, spec.bits, cp_top)}
{sar_logic(spec.bits, spec.vdd)}
.save {' '.join(save)} i(vdd) i(vref) i(vcm)
.tran {spec.tclk / 100:.4g} {tstop:.6g} 0 {spec.tclk / 25:.4g}
.control
set wr_singlescale
set wr_vecnames
option numdgt=8
run
wrdata wave.txt {' '.join(save)}
{meas}quit
.endc
.end
"""


def comparator_mc_testbench(spec, design: dict, n_inst: int, vspan: float, n_steps: int,
                            tclk: float) -> str:
    """`n_inst` comparators with independent mismatch, inp ramped across vcm +- vspan."""
    tstop = (n_steps + 1) * tclk
    inst = "\n".join(f"Xc{k} inp vcm clk qp{k} qn{k} vdd 0 strongarm" for k in range(n_inst))
    saves = " ".join(f"v(qp{k})" for k in range(n_inst))
    return f"""* comparator offset Monte Carlo (generated by sargen)
{lib_line(spec.corner, mismatch=True)}
.temp {spec.temp}
{strongarm_subckt(design['cmp'])}
Vdd vdd 0 {spec.vdd}
Vcm vcm 0 {spec.vcm}
Vinp inp 0 PWL(0 {spec.vcm - vspan} {tstop:.6g} {spec.vcm - vspan + 2 * vspan * (n_steps + 1) / n_steps})
Vclk clk 0 PULSE(0 {spec.vdd} {0.5 * tclk:.6g} {TR} {TR} {0.45 * tclk - TR:.6g} {tclk:.6g})
{inst}
.save {saves}
.tran {tclk / 100:.4g} {tstop:.6g} 0 {tclk / 25:.4g}
.control
set wr_singlescale
set wr_vecnames
run
wrdata wave.txt {saves}
quit
.endc
.end
"""


def unit_cells() -> dict:
    """Names of the primitive devices (for reporting)."""
    return dict(nfet=NFET, pfet=PFET, mim=MIM)
