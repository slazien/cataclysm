# Real Telemetry Data Sources for Track Reference

Research date: 2026-03-19
Providers used: Claude (3 agents), Codex (GPT-5.3), Gemini 2.5 Pro, direct web search

## Executive Summary

Finding actual downloadable telemetry files with GPS lat/lon for VIR, Laguna Seca,
and Road Atlanta is hard — most motorsport data is siloed in proprietary apps with
no public sharing. After exhaustive multi-provider research, here are the actionable paths:

| Priority | Source | Tracks | Format | Cost |
|----------|--------|--------|--------|------|
| ⭐ 1 | **iRacing self-sourcing** | All 3 | .ibt → lat/lon | ~$43 |
| ⭐ 2 | **LapSnap / Joel Ohman** | All 3 | AiM via app | Free-$9/mo |
| 3 | **Autosport Labs** | Laguna Seca | CSV (lat/lon) | Free |
| 4 | **TrailBrake.net** | Unknown | AiM files | Free |
| 5 | **Strava cycling** | Laguna Seca | GPX | Free |
| 6 | **racer-coder/TrackDataAnalysis** | iRacing | Python+GPS | Free |

---

## ⭐ Tier 1: Best Sources (Actionable Now)

### 1. iRacing Telemetry — Laser-Scanned GPS Data (ALL THREE TRACKS)

**The gold standard.** iRacing physically visits each track with rotating LIDAR to capture
360° point clouds + simultaneous GPS collection. Sub-centimeter surface accuracy.
Engineering time: ~13,000 person-hours per track. All coordinates are real-world WGS84.

| Track | iRacing Status | Cost |
|-------|---------------|------|
| **Laguna Seca** | Laser-scanned, original library | ~$15 |
| **Road Atlanta** | Laser-scanned | ~$15 |
| **VIR** | Rescanned 2022 (Full, Grand West, North, South, Patriot) | **FREE** (base content) |

**GPS channels confirmed (iRacing SDK docs):**
- `Lat` — float, decimal degrees, "Disk Only" (only in .ibt files)
- `Lon` — float, decimal degrees, "Disk Only"
- `Alt` — altitude in meters above sea level
- 60Hz sample rate

**How to get data:**
1. iRacing subscription (~$13/month)
2. Purchase tracks (Laguna ~$15, Road Atlanta ~$15, VIR = free)
3. On track → `Alt+L` to arm telemetry
4. `.ibt` files saved to `Documents/iRacing/Telemetry/`
5. **Total one-time cost: ~$43** (1 month sub + 2 track purchases)

**Python parsers:**
| Tool | URL | Notes |
|------|-----|-------|
| `pyirsdk` | github.com/kutu/pyirsdk | `ir['Lat']`, `ir['Lon']` directly |
| `racer-coder/TrackDataAnalysis` | github.com/racer-coder/TrackDataAnalysis | Opens IBT natively, GPS map with satellite bg |
| `Mu` | github.com/patrickmoore/Mu | Converts .ibt → MoTeC .ld (Windows GUI) |
| `teamjorge/ibt` | github.com/teamjorge/ibt | Go library, full parser |
| `ibt-telemetry` | github.com/SkippyZA/ibt-telemetry | Node.js, 100% complete parser |

**Practical workflow:**
1. Drive a slow clean lap → pure centerline trace
2. Parse .ibt with pyirsdk → extract Lat, Lon, Alt at each sample
3. Downsample/smooth → clean centerline polyline
4. Result: WGS84 GPS track centerline accurate to centimeters

---

### 2. LapSnap / Joel Ohman — Open Source Racing (ALL THREE TRACKS)

**The single best real-world telemetry source found.** Joel Ohman of "Open Source Racing"
shares professional MotoAmerica telemetry for ALL three tracks.

- **App**: LapSnap (iOS/Android) — https://lapsnap.app
- **Website**: https://opensource.racing
- **Article**: https://www.roadracingworld.com/news/lapsnap-telemetry-analysis-app-available-with-track-data/
- **Vehicle**: Suzuki GSX-R750 (MotoAmerica Supersport spec)
- **Data**: GPS traces, lap times, brake/throttle inputs, lean angle
- **Tracks**: Laguna Seca, VIR, Road Atlanta — plus all 2025 MotoAmerica calendar
- **Underlying format**: AiM .XRK/.DRK files (AiM Solo 2 hardware)
- **Access**: Download app → search "Joel Ohman" in Racers tab. Free to browse; subscription (~$9/month) for multiple sessions
- **Limitation**: Motorcycle data — speed/braking profiles differ from cars. GPS trace of track surface is still valid for our centerline needs.

---

### 3. Autosport Labs RaceCapture — Laguna Seca Sample CSV

Real-world GPS telemetry from a track car with RaceCapture/Pro hardware.

- **URL**: https://www.autosportlabs.com/racecapture-app-analysis-beta-available/
- **Forum**: https://forum.autosportlabs.com/viewtopic.php?t=3731 (page 7 has Dropbox link)
- **Format**: RaceCapture CSV (lat/lon, speed, accel, RPM, OBD-II channels)
- **Track**: Laguna Seca confirmed; also Sonoma and Thunderhill
- **Vehicle**: Unknown HPDE car
- **Limitation**: Dropbox link may be stale. VIR/Road Atlanta not confirmed.

---

## Tier 2: Worth Investigating

### 4. TrailBrake.net — AiM Data File Archive
- **Data files**: https://www.trailbrake.net/aim-files.html
- **Track maps**: https://www.trailbrake.net/aim-track-maps.html
- **Format**: AiM Race Studio 2 files (needs RS2/RS3 to view, exportable to CSV)
- **Contact**: matt@trailbrake.net for community contributions
- **Status**: Need to browse page directly to confirm which tracks are available

### 5. Traqmate Community — VIR Data
- **URL**: http://community.drivenasa.com/topic/17727-traqmate-sessions-for-shenandoah-and-vir-full/
- **Format**: Traqmate GPS files
- **Track**: VIR Full confirmed; Laguna Seca mentioned with corkscrew mapping issues
- **Limitation**: May be sparse

### 6. MiataNet Forum — AiM GPS Files for Laguna Seca
- **URL**: https://forum.miata.net/vb/archive/index.php/t-690663.html
- **Format**: AiM .drk and .gpk files
- **Vehicle**: MX-5 Miata
- **Track**: Laguna Seca; also Thunderhill and Sonoma
- **Access**: Register on forum, contact users who offered files

### 7. Strava Cycling Activities — Laguna Seca
- **Example activities**:
  - https://www.strava.com/activities/995043664 (vintage bike, 4.7 mi)
  - https://www.strava.com/activities/167406229 (4.6 mi)
- **Export**: Append `/export_gpx` to URL (requires account)
- **Quality**: Phone GPS (~5m), cycling speed — not racing line but real track surface
- **Tracks**: Laguna Seca confirmed. Road Atlanta/VIR need manual Strava search.

### 8. Popometer.io — iRacing Community Telemetry
- **Road Atlanta**: popometer.io/ir/setups/6711 (Porsche 963), 4497 (F4), 6587 (McLaren GT4)
- **VIR**: popometer.io/ir/setups/7593 (Ray F1600), 9581 (MX-5 Cup)
- **Laguna Seca**: popometer.io/ir/setups/8689 (Ray F1600)
- **Limitation**: Requires Coach Dave Academy subscription for data packs

### 9. ACC Replay Downloads — Laguna Seca Only
- **URL**: https://www.accreplay.com/leaderboards/laguna-seca
- **Cars**: Ferrari 296 GT3, BMW M4 GT3, McLaren 720S GT3, etc.
- **Format**: MoTeC .ld (parseable via github.com/gotzl/ldparser)
- **Limitation**: ACC does NOT embed real GPS coordinates; geometry only

### 10. HiPo Driver — VIR GPX Files
- **URL**: https://www.hipodriver.com/resources
- **Tracks**: VIR Full (PDR1+PDR2), VIR Grand (PDR1), VIR South (PDR2)
- **Format**: GPX finish line definitions for Corvette PDR
- **Limitation**: Waypoint definitions only, not full traces

### 11. Swift Navigation Piksi Multi — Laguna Seca
- **Referenced on**: selfracingcars.com (May 2017 event)
- **Data**: Inner/outer/centerline of Laguna Seca, RTK-GNSS (cm accuracy)
- **Status**: Download link not confirmed; referenced via Google Doc

---

## Tier 3: Not Applicable for Our Needs

| Source | Why Not |
|--------|---------|
| TUMFTM/racetrack-database | Only F1/DTM European tracks |
| RACECAR autonomous dataset | Only IMS/LVMS, not our tracks |
| Kaggle F1 datasets | Only F1 circuits |
| IndyCar open data | No public telemetry |
| RaceChrono community | No public sharing |
| VBOX Motorsport | No public data |
| Garmin Catalyst / Apex Pro | No public sharing |

---

## Recommended Action Plan

### Phase 1: Quick Wins (today)
1. **Download LapSnap app** → search Joel Ohman → extract GPS traces for all 3 tracks
2. **Browse TrailBrake.net AiM archive** → check which tracks available
3. **Check Autosport Labs forum** → find Dropbox link for Laguna Seca CSV
4. **Search Strava** for cycling activities on Road Atlanta and VIR

### Phase 2: iRacing Self-Source (1-2 days, ~$43)
1. Subscribe to iRacing ($13/month)
2. Purchase Laguna Seca ($15) + Road Atlanta ($15). VIR is free!
3. Drive 3-5 clean laps at each track (Alt+L for telemetry)
4. Parse .ibt files with pyirsdk:
   ```python
   import irsdk
   ir = irsdk.IRSDK()
   ir.startup(test_file='laguna_seca_lap.ibt')
   points = []
   while ir.get_new_data():
       lat, lon, alt = ir['Lat'], ir['Lon'], ir['Alt']
       speed, dist = ir['Speed'], ir['LapDist']
       if lat: points.append((lat, lon, alt, speed, dist))
   ```
5. Result: centimeter-accurate GPS racing lines for ALL 3 tracks

### Phase 3: Community Outreach
1. Post on r/CarTrackDays or r/HPDE for RaceChrono/TrackAddict exports
2. Contact MiataNet forum users for Laguna Seca AiM files
3. Check DrivenNASA community for VIR Traqmate sessions
4. Contact Swift Navigation about their Laguna Seca GNSS dataset

---

## Key Tools Reference

| Tool | URL | Purpose |
|------|-----|---------|
| pyirsdk | github.com/kutu/pyirsdk | Parse iRacing .ibt → Lat/Lon/Speed |
| TrackDataAnalysis | github.com/racer-coder/TrackDataAnalysis | IBT + AiM + MoTeC parser with GPS map |
| Mu | github.com/patrickmoore/Mu | Convert .ibt → MoTeC .ld |
| ldparser | github.com/gotzl/ldparser | Parse ACC MoTeC .ld files |
| gopro2gpx | github.com/juanmcasillas/gopro2gpx | Extract GPS from GoPro GPMF |
| LapSnap | lapsnap.app | Access Joel Ohman's racing telemetry |

---

## Appendix: Direct Download URLs (from Codex/Gemini research)

### Corvette PDR GPX Files — VIR (Direct URLs)
- VIR Full Course ZIP: https://www.hipodriver.com/s/VIR-Full.zip
- VIR Grand Course ZIP: https://www.hipodriver.com/s/VIR-Grand-Course.zip
- VIR Full Course GPX: https://www.hipodriver.com/s/VIR-Full.gpx
- VIR South Course GPX: https://www.hipodriver.com/s/VIR-South.gpx

### Laguna Seca PDR GPX — MidEngineCorvetteForum
- https://www.midenginecorvetteforum.com/forum/me-discussion-photos-videos/filedata/fetch?id=472381
- https://www.midenginecorvetteforum.com/forum/me-discussion-photos-videos/filedata/fetch?id=472382
- (Rename downloaded .txt → .gpx)

### ACC MoTeC Laguna Seca — Tortellini Coaching (Mega.nz)
- https://mega.nz/folder/AA8QDYZC#jCiziFmPcclGaM5h8oS9jw
- MoTeC .ld/.ldx, 1:19.9 GT3 lap. Parseable with gotzl/ldparser
- NOTE: ACC geometry only, no real-world GPS coordinates

### Garage61 — Free iRacing Community Telemetry
- https://garage61.net/
- Upload/browse/export iRacing telemetry as MoTeC .ld
- All three tracks available from community uploads

### IMSA Timing Data
- https://imsa.alkamelsystems.com/ — official sector times
- https://huggingface.co/datasets/tobil/imsa — HuggingFace dataset

### VBOX Track Map Database
- https://vboxmotorsport.co.uk/index.php/en/customer-area/track-map-database
- All three tracks as .tdb/.bdb definition files

### Forum Leads (Registration Required)
| Forum | Track | Format | URL |
|-------|-------|--------|-----|
| Rennlist | VIR (Porsche 981) | MoTeC .ld | rennlist.com/forums/.../1363608 |
| DrivenNASA | VIR Full | Traqmate | community.drivenasa.com/topic/17727 |
| MiataNet | Laguna Seca | AiM .drk | forum.miata.net/vb/archive/.../t-690663 |
| DrivenNASA | Road Atlanta | AiM .gpk | community.drivenasa.com/topic/22665 |
| Improved Touring | Road Atlanta | AiM .gpk | improvedtouring.com/threads/25808 |
| CorvetteForum | VIR + Road Atlanta | AiM/C5 data | corvetteforum.com/forums/.../4742787 |
| Laguna Seca GPX (Printables) | Laguna Seca | GPX | printables.com/model/737445 |
