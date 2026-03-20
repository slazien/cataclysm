# Sim Racing as Validation Data Source — Multi-Provider Research

**Date:** 2026-03-19
**Providers:** Claude (Sonnet), Codex (gpt-5.3-codex), Gemini (gemini-2.5-pro)
**Method:** Independent parallel research, synthesized after all completed

---

## Executive Summary

Sim racing lap times are **systematically 1-3% faster than real-world times** when car and track are matched. The gap is primarily caused by the absence of physical risk (not physics engine errors). Top-tier sims (iRacing, ACC, rFpro) achieve sub-1% accuracy on laser-scanned tracks with well-validated car models.

**Recommendation:** Sim lap times can serve as **secondary validation data** for our physics solver, with a +1.5% correction factor and appropriate caveats. This would unlock hundreds of data points across dozens of tracks.

---

## Accuracy by Simulator

| Sim | Typical Gap vs Real | Best Case | Use Case |
|-----|-------------------|-----------|----------|
| iRacing | 0-2% faster | 0.04% (Bathurst GT3) | Laser-scanned tracks, GT3/GT4, NASCAR |
| ACC | 0.7-3.2% faster | ~0% (Monza GT3) | GT3/GT4 specifically (official SRO license) |
| Assetto Corsa | 0-0.5% on quality content | 0.08% (F1 at Brands Hatch) | Broadest road car library |
| rFpro | Sub-1% | F1 teams use it | Professional only, not consumer |
| Forza | ~1.4% faster | FastestLaps 12-car study | Not suitable for validation |
| Gran Turismo | Not suitable | Simcade physics | Not suitable |

---

## Specific Documented Comparisons

| Track | Car | Real Time | Sim Time | Sim | Delta | Source |
|-------|-----|-----------|----------|-----|-------|--------|
| Bathurst | GT3 | 2:01.567 | 2:01.520 | iRacing | -0.04% | Reddit r/simracing |
| Brands Hatch | GT3 | 1:22.557 | 1:22.279 | iRacing | -0.34% | Reddit r/simracing |
| Nürburgring GP | GT3 | 1:55.832 | 1:52.112 | ACC | -3.21% | Reddit r/simracing |
| Brands Hatch | F1 (1997 Benetton) | 38.032s | ~38.0s | AC | -0.08% | Driver61 |
| Daytona | GTP | ~1:36 | ~1:33 | iRacing | ~-3% | OverTake.gg |
| Spa | GT3 (pole) | 2:16.375 | 2:15.137 | ACC | -0.9% | ACC Replay |
| Monza | GT3 (Emil Frey Jaguar) | 1:49.0 | 1:49.0 | ACC | ~0% | YouTube |

---

## Sources of Discrepancy (Consensus Ranked)

1. **Zero-risk driving** — sim drivers push harder, brake later, take more curb. Single biggest factor.
2. **Tire model approximations** — Pacejka-based models don't fully capture thermal cycling, non-linear wear, or contact patch deformation.
3. **Idealized track conditions** — sims default to perfect rubbered-in surface at optimal temperature. Real tracks have green/degraded patches, marbles, wind.
4. **Aero sensitivity** — lookup-table aero maps simplify ride-height/yaw/pitch dynamic effects. Worst for high-downforce cars.
5. **Braking system** — sim brakes don't fade or overheat like real carbon brakes. Sim braking distances are consistently shorter.
6. **Suspension compliance** — real bushings, camber curves, and anti-dive geometry simplified in sims.
7. **Driver fatigue/heat** — absent in sim. Real drivers lose ~0.5-1s/lap over a stint from physical stress.

---

## Per-Corner vs Total Lap Time

All 3 providers agree: **per-corner accuracy is surprisingly good** on well-modeled content. Braking points, minimum corner speeds, and throttle pickup positions match within 1-2 km/h. Total lap time accuracy sometimes benefits from error cancellation (too fast in one section, too slow in another).

**Implication for our solver:** Per-corner minimum speed from iRacing/ACC is more reliable than total lap time for validation purposes.

---

## Usability for Our Physics Solver Validation

### Yes, With These Conditions:
1. **Only laser-scanned tracks** — iRacing and ACC
2. **Apply +1.5% correction** to sim hotlap times (sims are faster due to zero-risk driving)
3. **Use `source_quality: "sim"` and `driver_level: "sim_pro"`** — separate category in analysis
4. **GT3/GT4 data is most reliable** — these cars are the focus of sim developers' validation efforts
5. **Road car data from AC is less reliable** — quality varies by mod, no official validation
6. **Expected error margin: ±1-2%** for well-validated car+track combos

### NOT Suitable:
- Forza Motorsport or Gran Turismo data
- Community mods without validation
- Non-laser-scanned tracks
- Data from older sim versions (physics patches invalidate old benchmarks)

---

## Academic References

- **MIT Presence (2011)**: Fastest-lap correlation r=0.57 between sim and real racing events
- **FISITA 2020 (TU Graz)**: Absolute behavioral validity 40-59%, motion platform improved by 1.3-3.3%
- **ScienceDirect CHBR (2024)**: 174 drivers, 1327 ACC laps at Brands Hatch — speed and lateral accel are dominant performance predictors (same as real racing)
- **SAE 2016-36-0164**: OptimumLap vs Formula SAE, 5-10% tolerance
- **PLOS ONE (2021)**: Professional sim provides "close-to-real emulation of physics and vehicle dynamics"

---

## Key Sources
- Driver61: https://driver61.com/sim-racing/how-do-real-f1-sim-f1-compare/
- FastestLaps Forza study: https://fastestlaps.com/articles/real-life-vs-forza-motorsport-4
- OverTake.gg Daytona: https://www.overtake.gg/news/sim-racing-vs-real-life-comparing-daytona-24-hour-lap-times.1762/
- iRacing physics: https://www.iracing.com/accuracy-v-precision-or-the-zen-of-iracing/
- ACC Spa comparison: https://www.assettocorsa.net/forum/index.php?threads/comparison-times-on-the-real-lap-vs-acc-track-spa.59485/
- Reddit GT3 comparison: https://www.reddit.com/r/simracing/comments/1iac3us/
- rFpro NISMO: https://rfpro.com/nismo-adopts-rfpro-for-its-driver-in-the-loop-simulation/
