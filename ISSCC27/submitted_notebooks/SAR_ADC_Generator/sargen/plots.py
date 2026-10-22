"""Figures for the SAR ADC report (all saved as PNG)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def waveforms(w, timing, spec, path):
    """Transient of a few conversions: top plate vs vcm, comparator clock/output, bits."""
    t = w["time"] * 1e9
    n = spec.bits
    fig, ax = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True,
                           gridspec_kw=dict(height_ratios=[2.2, 1, 1.6]))
    ax[0].plot(t, w["top"], label="top plate Vx")
    ax[0].axhline(spec.vcm, color="k", ls="--", lw=1, label="Vcm")
    for i in range(n):
        ax[0].plot(t, w[f"bot_{i}"], lw=0.8, alpha=0.7, label=f"bottom plate b{i}")
    ax[0].set_ylabel("V")
    ax[0].legend(ncol=3, fontsize=8, loc="upper right")
    ax[0].set_title("CDAC: sampling, then binary search (top plate converges to Vcm)")
    ax[1].plot(t, w["clk"], label="comparator clk")
    ax[1].plot(t, w["qp"], label="qp (1 = keep bit)")
    ax[1].plot(t, w["phit"], label="phi_top (sample)", alpha=0.7)
    ax[1].legend(ncol=3, fontsize=8, loc="upper right")
    ax[1].set_ylabel("V")
    for i in range(n):
        ax[2].plot(t, w[f"bo_{i}"] / spec.vdd * 0.8 + i, label=f"b{i}")
        ax[2].text(t[0], i + 0.2, f"b{i}", fontsize=8)
    ax[2].set_yticks([])
    ax[2].set_xlabel("time [ns]")
    ax[2].set_title("output bits")
    for k in range(1, int(t[-1] * 1e-9 / timing.tconv) + 1):
        for a in ax:
            a.axvline(k * timing.tconv * 1e9, color="grey", lw=0.6, ls=":")
    return _save(fig, path)


def transfer(vin, codes, spec, path):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.step(vin, codes, where="post", label="simulated (SPICE)")
    ideal = np.clip(np.floor(vin / spec.lsb), 0, 2**spec.bits - 1)
    ax.plot(vin, ideal, "--", alpha=0.7, label="ideal")
    ax.set_xlabel("Vin [V]")
    ax.set_ylabel("output code")
    ax.set_title(f"{spec.bits}-bit transfer characteristic")
    ax.grid(alpha=0.3)
    ax.legend()
    return _save(fig, path)


def inl_dnl(hist_res, spec, path, title="code-density test"):
    fig, ax = plt.subplots(3, 1, figsize=(8, 7.5))
    codes = np.arange(2**spec.bits)
    ax[0].bar(codes, hist_res["hist"], color="#4C9BE8")
    ax[0].set_ylabel("hits")
    ax[0].set_title(f"Histogram ({title})")
    ax[1].bar(hist_res["codes"], hist_res["dnl"], color="#E8744C")
    ax[1].set_ylabel("DNL [LSB]")
    ax[1].set_title(f"DNL (max |DNL| = {hist_res['dnl_max']:.3f} LSB)")
    ax[2].plot(hist_res["codes"], hist_res["inl"], "o-", color="#2E7D32")
    ax[2].set_ylabel("INL [LSB]")
    ax[2].set_xlabel("code")
    ax[2].set_title(f"INL, end-point fit (max |INL| = {hist_res['inl_max']:.3f} LSB)")
    for a in ax:
        a.grid(alpha=0.3)
    return _save(fig, path)


def spectrum(fft_res, spec, path):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    f = fft_res["freq_bins"] * spec.fs / 1e6
    # bins with no power at all (the fs/2 bin of a half-wave-symmetric coherent record is exactly 0) would dive
    # to the log floor (-300 dB): leave them out
    db = np.where(fft_res["spectrum_dbfs"] < -250, np.nan, fft_res["spectrum_dbfs"])
    ax.plot(f[1:], db[1:], lw=1)
    for k in fft_res["harmonic_bins"]:
        ax.plot(f[k], fft_res["spectrum_dbfs"][k], "rx")
    ax.set_xlabel("frequency [MHz]")
    ax.set_ylabel("power [dB rel. signal]")
    ax.set_title(f"FFT: SNDR = {fft_res['sndr_db']:.2f} dB, ENOB = {fft_res['enob']:.2f} bit, "
                 f"SFDR = {fft_res['sfdr_db']:.1f} dB  (ideal SQNR {fft_res['ideal_sqnr_db']:.1f} dB)",
                 fontsize=10)
    ax.grid(alpha=0.3)
    return _save(fig, path)


def time_samples(vin, codes, spec, path):
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(vin / spec.lsb, ".-", lw=0.6, label="Vin / LSB")
    ax.step(np.arange(len(codes)), codes, where="mid", label="output code")
    ax.set_xlabel("sample")
    ax.set_ylabel("LSB")
    ax.legend()
    ax.grid(alpha=0.3)
    ax.set_title("sine input vs. output code")
    return _save(fig, path)


def offset_hist(off, spec, path):
    off = np.asarray(off) * 1e3
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(off, bins=20, color="#8E6CC2")
    ax.set_xlabel("comparator offset [mV]")
    ax.set_ylabel("count")
    ax.set_title(f"Comparator offset Monte Carlo: mean {off.mean():.2f} mV, sigma {off.std(ddof=1):.2f} mV "
                 f"(LSB = {spec.lsb * 1e3:.1f} mV)", fontsize=10)
    ax.grid(alpha=0.3)
    return _save(fig, path)


def mc_linearity(dnl_max, inl_max, spec, path):
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].hist(dnl_max, bins=30, color="#E8744C")
    ax[0].set_xlabel("max |DNL| [LSB]")
    ax[0].set_title(f"DNL over Monte Carlo: 99th pct {np.percentile(dnl_max, 99):.3f} LSB")
    ax[1].hist(inl_max, bins=30, color="#2E7D32")
    ax[1].set_xlabel("max |INL| [LSB]")
    ax[1].set_title(f"INL over Monte Carlo: 99th pct {np.percentile(inl_max, 99):.3f} LSB")
    for a in ax:
        a.set_ylabel("count")
        a.grid(alpha=0.3)
    fig.suptitle(f"{spec.bits}-bit, {len(dnl_max)} mismatch samples (behavioral model with PDK sigma)")
    return _save(fig, path)


def transition_inl_dnl(tr, spec, path):
    """INL/DNL from measured code-transition voltages; also shows absolute INL (offset + gain)."""
    k = np.arange(1, 2**spec.bits)
    inl = np.asarray(tr["inl"])
    inl_ep = inl - np.linspace(inl[0], inl[-1], len(inl))
    fig, ax = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
    ax[0].bar(k[:-1] + 0.5, tr["dnl"], color="#E8744C")
    ax[0].set_ylabel("DNL [LSB]")
    ax[0].set_title(f"Transition-level DNL (max |DNL| = {tr['dnl_max']:.3f} LSB)")
    ax[1].plot(k, inl_ep, "o-", color="#2E7D32", label="end-point fit")
    ax[1].plot(k, inl, ".--", color="grey", alpha=0.7, label="absolute (incl. offset/gain)")
    ax[1].set_ylabel("INL [LSB]")
    ax[1].set_xlabel("code transition k")
    ax[1].set_title(f"Transition-level INL (max |INL| = {tr['inl_max']:.3f} LSB, end-point)")
    ax[1].legend(fontsize=8)
    for a in ax:
        a.grid(alpha=0.3)
    return _save(fig, path)
