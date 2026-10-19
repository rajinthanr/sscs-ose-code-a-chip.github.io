"""Specification-driven sizing of the SAR ADC from characterized PDK data.

Every decision is logged as a (block, rule, numbers, result) row so the notebook
can show *why* each device has its size.
"""

import math

from .pdk import L_MIN, MIM_MIN_SIDE, W_MIN

K_B = 1.380649e-23


def _ceil(x, grid=0.05):
    return math.ceil(x / grid - 1e-9) * grid


class Log(list):
    def add(self, block, rule, numbers, result):
        self.append(dict(block=block, rule=rule, numbers=numbers, result=result))


def size_sar(spec, char: dict) -> dict:
    N, lsb, T = spec.bits, spec.lsb, spec.tclk
    kT = K_B * (spec.temp + 273.15)
    log = Log()
    log.add("spec", "LSB = Vref / 2^N", f"{spec.vref} V / {2**N}", f"{lsb * 1e3:.2f} mV")
    log.add("timing", "Tclk = 1 / ((N + 2) * fs)", f"fs = {spec.fs / 1e6:g} MS/s, {N + 2} cycles",
            f"{T * 1e9:.2f} ns ({spec.fclk / 1e6:.1f} MHz)")

    # ---------------------------------------------------------------- unit capacitor
    ln_settle = math.log(2**N / spec.settle_lsb)       # time constants to settle to settle_lsb
    sig_u = spec.dnl_3sigma_lsb / (3 * math.sqrt(2**N - 1))
    a_c = char["mim_match_pct_um"] / 100
    side_match = a_c / sig_u
    log.add("CDAC", "sigma_DNL(mid-code) = sqrt(2^N - 1) * sigma_u <= DNL_3sigma / 3",
            f"sigma_u <= {sig_u * 100:.3f} %, A_C = {char['mim_match_pct_um']} %um",
            f"side >= {side_match:.2f} um (matching)")
    ca, cp = char["mim_ca_fF_um2"] * 1e-15, char["mim_cp_fF_um"] * 1e-15
    c_of = lambda s: ca * s * s + cp * 4 * s       # noqa: E731
    sig_ktc = spec.noise_lsb * lsb
    c_ktc = kT / sig_ktc**2
    # solve 2^N * (ca s^2 + 4 cp s) = C_kTC for s
    side_ktc = (-4 * cp + math.sqrt(16 * cp**2 + 4 * ca * c_ktc / 2**N)) / (2 * ca)
    log.add("CDAC", "kT/C: sqrt(kT / C_total) <= noise_lsb * LSB",
            f"C_total >= {c_ktc * 1e15:.3g} fF",
            f"side >= {side_ktc:.2f} um (noise)" if side_ktc >= 0.01 else "negligible at this resolution")
    side = _ceil(max(side_match, side_ktc, MIM_MIN_SIDE))
    cu = c_of(side)
    c_tot = 2**N * cu
    reason = max([("matching", side_match), ("kT/C", side_ktc), ("min. size", MIM_MIN_SIDE)],
                 key=lambda x: x[1])[0]
    log.add("CDAC", "Cu = Ca * s^2 + Cp * 4s (characterized MIM)",
            f"s = {side:.2f} um, limited by {reason}",
            f"Cu = {cu * 1e15:.2f} fF, C_total = {c_tot * 1e15:.1f} fF")

    # ---------------------------------------------------------------- comparator
    sig_os_t = spec.offset_3sigma_lsb * lsb / 3
    wl_in = (char["avt_n_mVum"] * 1e-3 / sig_os_t) ** 2
    l_in = 0.3
    w_in = _ceil(max(wl_in / l_in, 2.0), 0.1)
    sig_os_est = char["avt_n_mVum"] * 1e-3 / math.sqrt(w_in * l_in)
    log.add("comparator", "sigma_os ~ A_VT / sqrt(W L) <= offset_3sigma * LSB / 3",
            f"A_VT = {char['avt_n_mVum']:.2f} mVum, target {sig_os_t * 1e3:.2f} mV",
            f"W L >= {wl_in:.3f} um^2 -> W/L = {w_in:.1f}/{l_in} (est. {sig_os_est * 1e3:.2f} mV)")
    preamp = wl_in > 20.0
    log.add("comparator", "pre-amplifier needed if W L > 20 um^2 (input cap / kick-back)",
            f"W L = {wl_in:.2f} um^2", "YES - add preamp" if preamp else "no - StrongARM alone")
    cmp_ = dict(w_in=w_in, l_in=l_in, w_tail=_ceil(1.5 * w_in, 0.1), w_ln=_ceil(max(w_in / 2, 1.0), 0.1),
                w_lp=_ceil(max(w_in / 2, 1.0), 0.1), w_rst=1.0, w_inv_n=1.0, w_inv_p=2.0, l=L_MIN,
                sigma_os_target=sig_os_t, sigma_os_est=sig_os_est, preamp=preamp)
    log.add("comparator", "tail = 1.5 W_in, latch = W_in / 2, reset / inverters fixed",
            "", f"tail {cmp_['w_tail']}, nlatch {cmp_['w_ln']}, platch {cmp_['w_lp']} um")

    # ---------------------------------------------------------------- sampling switches
    t_track = 0.85 * T
    tau_s = t_track / ln_settle
    r_unit = tau_s / 2 / cu                    # half of the budget for the bit switch ...
    r_top = tau_s / 2 / c_tot                  # ... half for the shared top-plate switch
    rw_tg = char["ron_tg_ohm_um"]
    in_wn = _ceil(max(rw_tg / r_unit, W_MIN))
    top_wn = _ceil(max(rw_tg / r_top, W_MIN))
    log.add("sampling", "tau = T_track / ln(2^N / settle_lsb); split between bit and top switch",
            f"T_track = {t_track * 1e9:.2f} ns, tau <= {tau_s * 1e12:.0f} ps",
            f"R_unit <= {r_unit / 1e3:.1f} kOhm, R_top <= {r_top:.0f} Ohm")
    log.add("sampling", "W_n = (R_on W)_TG,worst / R  (Wp = 2 Wn), bit-i switch = 2^i units",
            f"(R_on W) = {rw_tg / 1e3:.2f} kOhm um", f"unit TG {in_wn:.2f}/{2 * in_wn:.2f} um, "
            f"top TG {top_wn:.2f}/{2 * top_wn:.2f} um")

    # ---------------------------------------------------------------- DAC drivers
    t_dac = 0.45 * T                          # DAC must settle before the comparator clock
    tau_d = t_dac / ln_settle
    r_drv = tau_d / cu / 2                    # driver + top-plate redistribution, 2x margin
    drv = dict(wn=_ceil(max(char["ron_n_ohm_um"] / r_drv, W_MIN)),
               wp=_ceil(max(char["ron_p_ohm_um"] / r_drv, W_MIN)))
    log.add("DAC driver", "tau = 0.45 Tclk / ln(2^N / settle_lsb), per unit cap (binary scaled)",
            f"tau <= {tau_d * 1e12:.0f} ps, R_unit <= {r_drv / 1e3:.1f} kOhm",
            f"unit NMOS {drv['wn']:.2f} um, unit PMOS {drv['wp']:.2f} um")

    design = dict(
        bits=N, cu=dict(side=side, c=cu, c_total=c_tot, sigma_u=a_c / side),
        cmp=cmp_, sw=dict(in_wn=in_wn, in_wp=2 * in_wn, top_wn=top_wn, top_wp=2 * top_wn),
        drv=drv, l_sw=L_MIN,
        timing=dict(tclk=T, t_track=t_track, t_dac=t_dac),
        noise=dict(ktc_rms=math.sqrt(kT / c_tot)),
    )
    design["log"] = list(log)
    return design


def sizing_table_md(design: dict) -> str:
    rows = ["| block | rule | numbers | result |", "|---|---|---|---|"]
    rows += [f"| {r['block']} | {r['rule']} | {r['numbers']} | **{r['result']}** |" for r in design["log"]]
    return "\n".join(rows)
