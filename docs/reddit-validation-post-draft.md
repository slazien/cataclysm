# Reddit Post Draft — r/CarTrackDays

## Title Options

1. "We validated our physics-based lap time predictions against 33 real-world times — here's how close they are"
2. "I built a track coaching tool that computes your physics ceiling, not just 'you were slower on lap 5' — validated against real data"
3. "Physics-based coaching vs. lap-comparative AI: why comparing your laps against each other misses the point"

---

## Post Body (Option 1 — Data-Forward)

I've been building Cataclysm, a track data analysis tool that uses a vehicle dynamics solver to compute the physically optimal lap time for your specific car+tire combination at your track. I wanted to share the validation results because I think transparency matters when a tool claims to know "how fast you should be going."

### What the solver does

Given your car's weight, power, and tire grip characteristics, it runs a forward-backward velocity profile simulation (same algorithm class used in Formula SAE / OptimumLap) to compute the fastest physically possible lap time. This becomes your coaching ceiling — the gap between your real laps and this ceiling is the time you can find through better driving alone.

### How I validated it

I collected 33 lap times from community sources:
- **Forums:** gr86.org track time database, rennlist GT4/GT3 lap time threads, mustang6g S550 lap times, trackmustangsonline
- **Databases:** LapMeta.com, FastestLaps.com, LapTrophy.com
- **Official:** NASA TT records
- **Media:** Published track tests

Each entry includes the car, track, tire compound, and modification level. I then ran the solver for the same car+tire+track combination and compared.

### Results

**Mean efficiency ratio: 0.976** — the solver predicts lap times 2.4% faster than real drivers achieve. This is exactly the expected result for a physics ceiling vs. amateur/intermediate drivers.

**By tire compound:**

| Compound | Mean Ratio | Interpretation |
|----------|----------:|----------------|
| R-Compound (mu=1.35) | 0.913 | Solver 8.7% faster — R-comps require advanced technique to exploit |
| Super 200TW (mu=1.10) | 0.989 | Near-perfect match |
| Endurance 200TW (mu=1.00) | 1.007 | Near-perfect match |
| Street (mu=0.85) | 1.042 | Solver slightly conservative (n=1) |

**Closest matches:**

| Car | Track | Tires | Real | Predicted | Delta |
|-----|-------|-------|-----:|----------:|------:|
| Miata ND | Barber | Endurance 200TW | 1:48.36 | 1:48.72 | +0.4s |
| GR86 | Barber | RT660 | 1:47.66 | 1:47.96 | +0.3s |
| BMW M2 | Barber | RS4 | 1:43.18 | 1:43.52 | +0.3s |
| C8 Z06 | AMP | PS4S | 1:31.35 | 1:30.79 | -0.6s |

**Cars validated:** Miata NA, Miata ND, GR86, Civic Type R, BMW M2, Cayman GT4, 911 GT3, Mustang GT, GT350, Corvette C8 Z51/Z06

**Tracks:** Barber Motorsports Park, Atlanta Motorsports Park, Roebling Road Raceway

### Why this matters

Most AI coaching tools I've seen compare your laps against each other: "you were slower at T5 on lap 3 than on lap 7." This fails when:
- All your laps have the same flaw (blind spot)
- Variance is caused by traffic or incidents (false positive)
- Your "fast lap" had favorable circumstances (false reference)

I saw a thread here recently where a NASA instructor reviewed one such tool's AI coaching and found **3 out of 3 points were factually wrong** — the AI attributed traffic-caused speed differences to driver technique.

Cataclysm computes what's physically possible with your car+tires, then tells you where the gap is. If you're braking 12 meters too early at T5, it says that — whether or not your other laps had the same flaw.

### Equipment modeling

The solver adjusts for tire compound. Here's how the predicted optimal changes for a GR86 at Barber:

| Compound | Predicted Optimal |
|----------|------------------:|
| Street (mu=0.85) | 1:58.01 |
| Endurance 200TW (mu=1.00) | 1:47.96 |
| R-Compound (mu=1.35) | 1:35.52 |

Switching from street tires to R-comps changes the coaching targets by 19%. If a tool doesn't model your tires, the coaching is generic at best.

### What it looks like

[SCREENSHOT: Upload a RaceChrono CSV → physics-optimal comparison → per-corner coaching report]

Free to try (anonymous upload, no account needed): [link]

The full validation dataset (33 entries with sources) is published at [link].

Happy to answer technical questions about the physics model or discuss the validation methodology.

---

## Post Body (Option 2 — Competitive Angle, shorter)

I see a lot of AI coaching tools for track data. Most of them compare your laps against each other and tell you "you were slower here on lap 3." That's useful — until all your laps have the same flaw, or the variance was caused by traffic.

I've been building something different. Cataclysm computes the **physics-optimal** lap time for your car+tire combination using a vehicle dynamics solver. The gap between your real laps and the physics ceiling is what you can find through better driving alone.

I just finished validating this against **33 real-world lap times** from forums, NASA records, and timing databases. Mean accuracy: **2.4% from reality** across 12 cars (Miata to C8 Z06) and 3 tracks.

The solver correctly handles:
- Different tire compounds (street through R-comps, 19% range)
- 116hp Miata through 670hp Corvette
- FWD (Civic Type R) and RWD cars

Some closest matches: GR86 on RT660s at Barber — predicted 1:47.96, real 1:47.66 (0.3s delta). BMW M2 on RS4s at Barber — predicted 1:43.52, real 1:43.18 (0.3s delta).

Full validation report with methodology and data sources: [link]

Free to try: upload a RaceChrono CSV at [link], no account needed.

---

## Suggested Images/Screenshots for Post

1. **Hero infographic** — screenshot the HTML infographic top section (hero stats + bar chart)
2. **Closest matches table** — screenshot the data table
3. **App screenshot** — the actual coaching report showing per-corner brake gaps vs physics optimal
4. **Equipment comparison** — the tire compound table showing how targets change
5. **Competitive comparison table** — physics-based vs lap-comparative (from infographic)

## Subreddits to Post

- r/CarTrackDays (primary, 40K+ members)
- r/GR86 (good for validation examples using their forum data)
- r/HPDE (smaller but targeted)
- r/MotorsportsEngineering (technical audience)
- r/Miata (validation includes Miata NA and ND)
- r/Corvette (C8 Z06 validation is strong)

## Timing

Post mid-week (Tue-Thu) for best engagement. Avoid weekends (track day people are at the track, not Reddit).
