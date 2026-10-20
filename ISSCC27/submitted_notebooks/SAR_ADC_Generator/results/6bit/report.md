# 6-bit SAR ADC - generated report

**Spec:** 6 bit, 10 MS/s, Vref = 1.8 V, LSB = 28.12 mV, SKY130 tt, 27.0 C

## Sizing
| block | rule | numbers | result |
|---|---|---|---|
| spec | LSB = Vref / 2^N | 1.8 V / 64 | **28.12 mV** |
| timing | Tclk = 1 / ((N + 2) * fs) | fs = 10 MS/s, 8 cycles | **12.50 ns (80.0 MHz)** |
| CDAC | sigma_DNL(mid-code) = sqrt(2^N - 1) * sigma_u <= DNL_3sigma / 3 | sigma_u <= 2.100 %, A_C = 2.8 %um | **side >= 1.33 um (matching)** |
| CDAC | kT/C: sqrt(kT / C_total) <= noise_lsb * LSB | C_total >= 0.524 fF | **side >= 0.01 um (noise)** |
| CDAC | Cu = Ca * s^2 + Cp * 4s (characterized MIM) | s = 2.00 um, limited by min. size | **Cu = 9.32 fF, C_total = 596.3 fF** |
| comparator | offset only shifts the transfer curve here (no DNL/INL): spec = offset error | 3 sigma_os <= 1.0 LSB | **sigma_os <= 9.38 mV** |
| comparator | sigma_os ~ A_VT / sqrt(W L) <= offset_3sigma * LSB / 3 | A_VT = 7.38 mVum, target 9.38 mV | **W L >= 0.619 um^2 -> W/L = 2.1/0.3 (est. 9.29 mV)** |
| comparator | pre-amplifier needed if W L > 20 um^2 (input cap / kick-back) | W L = 0.62 um^2 | **no - StrongARM alone** |
| comparator | tail = 1.5 W_in, latch = W_in / 2, reset / inverters fixed |  | **tail 3.2, nlatch 1.1, platch 1.1 um** |
| sampling | TG device flavour = lowest worst-case R_on W (ss/-40C, ss/125C, tt/-10% supply) | std: 434.9 kOhm um, lvt: 7.4 kOhm um | **lvt transistors** |
| sampling | tau = T_track / ln(2^N / settle_lsb); 1/4 bit switch, 3/4 top switch | T_track = 10.62 ns, tau <= 1916 ps | **R_unit <= 51.4 kOhm, R_top <= 2410 Ohm** |
| sampling | W_n = (R_on W)_TG,worst / R  (Wp = 2 Wn), bit-i switch = 2^i units | worst (R_on W) = 7.45 kOhm um (ss -40C 1.80V) | **unit TG 0.45/0.90 um, top TG 3.10/6.20 um** |
| DAC driver | tau = 0.45 Tclk / ln(2^N / settle_lsb), per unit cap (binary scaled) | tau <= 1014 ps, R_unit <= 54.4 kOhm | **unit NMOS 0.45 um, unit PMOS 0.45 um** |

## Results (transistor level, pre-layout)
| metric | value |
|---|---|
| ENOB (FFT, 1.016 MHz) | **6.01 bit** (ideal quantizer: 6.14) |
| SNDR / SFDR / THD | 37.94 dB / 47.2 dB / -51.3 dB |
| max DNL / INL (histogram) | 0.145 / 0.138 LSB |
| max DNL / INL (transition levels) | 0.206 / 0.202 LSB |
| missing codes | 0 |
| offset / gain error | -0.262 / 0.017 LSB |
| comparator offset sigma (MC, n=192) | 8.26 mV (0.294 LSB) |
| power (comparator + CDAC + switches + SAR logic cells) | 33.82 uW |
| energy / conversion | 3.382 pJ |
| Walden FoM | 52.5 fJ/conv-step |
| MC (1000 runs) 99th-pct DNL / INL | 0.302 / 0.175 LSB |
| MC yield (max DNL < 0.5 LSB) | 100.0 % |

Runtime: 1062 s
