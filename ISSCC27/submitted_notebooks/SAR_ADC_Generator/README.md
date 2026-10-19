# SARGen - automated, explainable SAR ADC generator (SKY130)

IEEE SSCS Code-a-Chip, ISSCC 2027 submission (work in progress).

**Author:** Rajinthan Rameshkumar, Dept. of Electronic and Telecommunication Engineering,
University of Moratuwa, Sri Lanka (rajinthan519@gmail.com, [rajinthan.com](https://rajinthan.com))

Enter a resolution (4-8 bit) and a sample rate; the flow characterizes the SKY130 PDK, sizes the
SAR ADC, generates a transistor-level netlist, simulates it with ngspice and reports ENOB, INL/DNL,
histogram, FFT, comparator offset, power and Monte-Carlo yield, together with an animated explanation
of the conversion.

## Quick start

All tools come from the [IIC-OSIC-TOOLS](https://github.com/iic-jku/IIC-OSIC-TOOLS) container (tag `2026.10`).

```bash
# headless, from this folder inside the container
python3 run_flow.py --bits 4            # results in build/4bit/
python3 run_flow.py --bits 6 --fs 5e6   # any resolution 4..8

# or open the notebook
jupyter lab SAR_ADC_Generator.ipynb
```

## Flow

| stage | module | what it does |
|---|---|---|
| spec | `sargen/spec.py` | N, fs, Vref, corner, LSB-based targets (DNL, offset, noise, settling) |
| characterize | `sargen/characterize.py` | ngspice: A_VT (nfet/pfet), TG and driver R_on x W, MIM density; MIM matching from the PDK model |
| size | `sargen/sizing.py` | unit cap (matching vs kT/C vs min size), StrongARM (offset, preamp decision), switches and drivers (settling); every decision logged |
| netlist | `sargen/netlist.py` | MIM unit-cap CDAC, transmission gates, binary-scaled drivers, StrongARM, XSPICE SAR logic, timing |
| simulate | `sargen/spice.py`, `sargen/flow.py` | single conversion, comparator offset MC, ramp (histogram), coherent sine (FFT); chunks run in parallel |
| measure | `sargen/metrics.py` | DNL/INL (code density and transition levels), SNDR/SFDR/THD/ENOB, Walden FoM |
| explain | `sargen/model.py`, `sargen/anim.py` | behavioral model (PDK-calibrated MC) and animated binary search |

## Architecture (current)

Single-ended, binary-weighted charge-redistribution CDAC with bottom-plate sampling; MSB is set at the
end of sampling (keeps the top plate inside the supply rails); StrongARM comparator against Vcm = Vref/2;
synchronous SAR logic. Input range 0..Vref.

Idealizations (stated in the results): SAR logic and phase generation are ideal XSPICE / voltage sources
(no logic power), Vref and Vcm are ideal sources, no layout parasitics yet.

## Roadmap

- [x] 4-bit pre-layout flow: characterization, sizing, netlist, ramp/FFT/MC metrics, animation
- [ ] gLayout generators: common-centroid MIM array, StrongARM, switches
- [ ] DRC/LVS (Magic, Netgen, KLayout) and PEX, post-layout re-simulation
- [ ] 4..8-bit sweep with ENOB / power / area / FoM trends

## License

Apache-2.0 (see `LICENSE`).
