# 4-bit SAR ADC - generated report

**Spec:** 4 bit, 10 MS/s, Vref = 1.8 V, LSB = 112.50 mV, SKY130 tt, 27.0 C

## Sizing
| block | rule | numbers | result |
|---|---|---|---|
| spec | LSB = Vref / 2^N | 1.8 V / 16 | **112.50 mV** |
| timing | Tclk = 1 / ((N + 2) * fs) | fs = 10 MS/s, 6 cycles | **16.67 ns (60.0 MHz)** |
| CDAC | sigma_DNL(mid-code) = sqrt(2^N - 1) * sigma_u <= DNL_3sigma / 3 | sigma_u <= 4.303 %, A_C = 2.8 %um | **side >= 0.65 um (matching)** |
| CDAC | kT/C: sqrt(kT / C_total) <= noise_lsb * LSB | C_total >= 0.0327 fF | **negligible at this resolution** |
| CDAC | Cu = Ca * s^2 + Cp * 4s (characterized MIM) | s = 2.00 um, limited by min. size | **Cu = 9.32 fF, C_total = 149.1 fF** |
| comparator | offset only shifts the transfer curve here (no DNL/INL): spec = offset error | 3 sigma_os <= 1.0 LSB | **sigma_os <= 37.50 mV** |
| comparator | sigma_os ~ A_VT / sqrt(W L) <= offset_3sigma * LSB / 3 | A_VT = 7.38 mVum, target 37.50 mV | **W L >= 0.039 um^2 -> W/L = 2.0/0.3 (est. 9.52 mV)** |
| comparator | pre-amplifier needed if W L > 20 um^2 (input cap / kick-back) | W L = 0.04 um^2 | **no - StrongARM alone** |
| comparator | tail = 1.5 W_in, latch = W_in / 2, reset / inverters fixed |  | **tail 3.0, nlatch 1.0, platch 1.0 um** |
| sampling | TG device flavour = lowest worst-case R_on W (ss/-40C, ss/125C, tt/-10% supply) | std: 434.9 kOhm um, lvt: 7.4 kOhm um | **lvt transistors** |
| sampling | tau = T_track / ln(2^N / settle_lsb); 1/4 bit switch, 3/4 top switch | T_track = 14.17 ns, tau <= 3406 ps | **R_unit <= 91.4 kOhm, R_top <= 17136 Ohm** |
| sampling | W_n = (R_on W)_TG,worst / R  (Wp = 2 Wn), bit-i switch = 2^i units | worst (R_on W) = 7.45 kOhm um (ss -40C 1.80V) | **unit TG 0.45/0.90 um, top TG 0.45/0.90 um** |
| DAC driver | tau = 0.45 Tclk / ln(2^N / settle_lsb), per unit cap (binary scaled) | tau <= 1803 ps, R_unit <= 96.8 kOhm | **unit NMOS 0.45 um, unit PMOS 0.45 um** |

## Results (transistor level, pre-layout)
| metric | value |
|---|---|
| ENOB (FFT, 1.016 MHz) | **3.96 bit** (ideal quantizer: 3.97) |
| SNDR / SFDR / THD | 25.58 dB / 34.7 dB / -32.0 dB |
| max DNL / INL (histogram) | 0.038 / 0.062 LSB |
| max DNL / INL (transition levels) | 0.063 / 0.081 LSB |
| missing codes | 0 |
| offset / gain error | -0.122 / -0.021 LSB |
| comparator offset sigma (MC, n=192) | 8.54 mV (0.076 LSB) |
| power (comparator + CDAC + switches + SAR logic cells) | 13.93 uW |
| energy / conversion | 1.393 pJ |
| Walden FoM | 89.7 fJ/conv-step |
| MC (1000 runs) 99th-pct DNL / INL | 0.130 / 0.083 LSB |
| MC yield (max DNL < 0.5 LSB) | 100.0 % |

Runtime: 369 s
