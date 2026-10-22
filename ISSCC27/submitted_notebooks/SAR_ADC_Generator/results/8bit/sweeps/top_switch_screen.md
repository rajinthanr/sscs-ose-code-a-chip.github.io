| top-plate switch | corner | R_on at Vcm [Ohm] | time constants in the tracking window (need 6.9) | droop over one conversion [LSB] | verdict |
|---|---|---|---|---|---|
| LVT N + LVT P (sized) | tt +27C 1.80V | 61 | 24.8 | 0.330 | leaks |
| LVT N + LVT P (sized) | ff +125C 1.80V | 53 | 28.8 | 15.800 | leaks |
| LVT N + LVT P (sized) | fs +125C 1.80V | 81 | 18.7 | 17.848 | leaks |
| LVT N + LVT P (sized) | sf -40C 1.80V | 42 | 36.5 | 0.000 | ok |
| LVT N + LVT P (sized) | ss -40C 1.80V | 93 | 16.3 | 0.000 | ok |
| LVT N + LVT P (sized) | ss -40C 1.62V | 257 | 5.9 | 0.000 | too slow |
| SVT N + SVT P | tt +27C 1.80V | 187 | 8.1 | 0.003 | ok |
| SVT N + SVT P | ff +125C 1.80V | 71 | 21.6 | 3.998 | leaks |
| SVT N + SVT P | fs +125C 1.80V | 98 | 15.5 | 6.441 | leaks |
| SVT N + SVT P | sf -40C 1.80V | 139 | 10.9 | 0.000 | ok |
| SVT N + SVT P | ss -40C 1.80V | 660 | 2.3 | 0.000 | too slow |
| SVT N + SVT P | ss -40C 1.62V | 3580 | 0.4 | 0.000 | too slow |
| SVT N + LVT P | tt +27C 1.80V | 105 | 14.5 | 0.330 | leaks |
| SVT N + LVT P | ff +125C 1.80V | 67 | 22.6 | 15.806 | leaks |
| SVT N + LVT P | fs +125C 1.80V | 99 | 15.3 | 17.851 | leaks |
| SVT N + LVT P | sf -40C 1.80V | 113 | 13.5 | 0.000 | ok |
| SVT N + LVT P | ss -40C 1.80V | 254 | 6.0 | 0.000 | too slow |
| SVT N + LVT P | ss -40C 1.62V | 690 | 2.2 | 0.000 | too slow |
| LVT N + SVT P | tt +27C 1.80V | 82 | 18.5 | 0.003 | ok |
| LVT N + SVT P | ff +125C 1.80V | 55 | 27.7 | 3.993 | leaks |
| LVT N + SVT P | fs +125C 1.80V | 80 | 18.9 | 6.438 | leaks |
| LVT N + SVT P | sf -40C 1.80V | 45 | 33.9 | 0.000 | ok |
| LVT N + SVT P | ss -40C 1.80V | 121 | 12.6 | 0.000 | ok |
| LVT N + SVT P | ss -40C 1.62V | 367 | 4.1 | 0.000 | too slow |
| LVT NMOS only, W_n | tt +27C 1.80V | 87 | 17.5 | 0.000 | ok |
| LVT NMOS only, W_n | ff +125C 1.80V | 80 | 19.1 | 0.064 | ok |
| LVT NMOS only, W_n | fs +125C 1.80V | 174 | 8.8 | 0.006 | ok |
| LVT NMOS only, W_n | sf -40C 1.80V | 45 | 33.9 | 0.000 | ok |
| LVT NMOS only, W_n | ss -40C 1.80V | 121 | 12.6 | 0.000 | ok |
| LVT NMOS only, W_n | ss -40C 1.62V | 367 | 4.1 | 0.000 | too slow |
| LVT NMOS only, 2 W_n | tt +27C 1.80V | 44 | 34.9 | 0.000 | ok |
| LVT NMOS only, 2 W_n | ff +125C 1.80V | 40 | 38.2 | 0.127 | ok |
| LVT NMOS only, 2 W_n | fs +125C 1.80V | 87 | 17.5 | 0.012 | ok |
| LVT NMOS only, 2 W_n | sf -40C 1.80V | 22 | 67.8 | 0.000 | ok |
| LVT NMOS only, 2 W_n | ss -40C 1.80V | 60 | 25.3 | 0.000 | ok |
| LVT NMOS only, 2 W_n | ss -40C 1.62V | 183 | 8.3 | 0.000 | ok |

Sized switch W_n / W_p = 33.95 / 67.9 um, C_total = 4.19 pF; droop limit 1/4 LSB; time constants from 3/4 of the tracking phase.
