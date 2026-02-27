# User Guide

Cataclysm is an AI-powered telemetry analysis platform for track day drivers. Upload your RaceChrono data and get instant coaching insights.

## Getting Started

### 1. Record Your Session

Use [RaceChrono Pro](https://racechrono.com/) with a GPS data logger to record your track day session.

**Minimum requirements**:
- GPS accuracy < 2.0m
- Satellite count >= 6
- Lap timing with start/finish line set

### 2. Export CSV

In RaceChrono:
1. Open your session
2. Tap "Export" → "CSV v3"
3. Save the file to your device

### 3. Upload to Cataclysm

1. Go to [cataclysm.up.railway.app](https://cataclysm.up.railway.app)
2. Sign in with your Google account
3. Click "Upload" in the top bar
4. Select your CSV file(s)
5. Wait for processing (typically 5-10 seconds)

### 4. Explore Your Data

Once uploaded, your session appears in the left sidebar. Click it to view the dashboard.

## Dashboard

The dashboard shows an overview of your session:

- **Session Score** — Composite rating (0-100) based on consistency, optimal line, and corner grades
- **Track Map** — Interactive 2D map of your laps with corner markers
- **Lap Times** — Bar chart of all lap times, highlighting personal bests
- **Time Gained** — Per-corner breakdown of where you gain/lose time
- **Skill Radar** — 6-axis radar chart: consistency, braking, cornering, throttle, line, adaptability
- **Top Priorities** — AI-identified areas for improvement
- **GPS Quality** — Accuracy metrics for your data
- **Weather** — Conditions during your session (auto-fetched)

## Deep Dive

Detailed telemetry analysis with 5 tabs:

### Speed Tab

Multi-lap speed overlay showing your speed at every point on track. Select laps from the sidebar to compare.

**Features**:
- Crosshair syncs across all charts when you hover
- Delta time chart shows where you gain/lose vs reference lap
- Brake/throttle traces show your inputs

### Corners Tab

Per-corner analysis with detailed KPIs:
- **Brake point** — Where you start braking (in meters before the corner)
- **Apex speed** — Minimum speed through the corner (mph)
- **Peak brake g** — Maximum deceleration force
- **Throttle commit** — Where you get back on throttle after the apex
- **Apex type** — Early, mid, or late apex

Click any corner on the track map to see its detail panel.

### Sectors Tab

Mini-sector breakdown divides the track into 20 equal segments. Each sector is color-coded:
- **Purple** — Personal best for that sector
- **Green** — Faster than average
- **Yellow** — Near average
- **Red** — Slower than average

### Replay Tab

Animated lap playback with speed gauge and position on track map.

## AI Coach

The AI coaching panel (accessible from the coach button) provides:

### Coaching Report

Automatically generated when you upload a session:
- **Summary** — Natural language overview of your driving
- **Priority Corners** — Top improvement opportunities with estimated time cost
- **Corner Grades** — Letter grades for braking, trail braking, min speed, and throttle at each corner
- **Patterns** — Identified driving habits (good and bad)
- **Drills** — Specific exercises to practice on your next session

### Chat

Ask follow-up questions to the AI coach:
- "How can I improve my braking into T5?"
- "Why is my apex speed low in T2?"
- "What should I focus on next session?"

The coach has full context of your telemetry data and will reference specific numbers from your session.

### Skill Level

Set your skill level in Settings to get appropriately targeted coaching:
- **Novice** — Focus on safety, smooth inputs, basic racing line
- **Intermediate** — Trail braking, weight transfer, optimal cornering
- **Advanced** — Tenths of seconds, advanced techniques, racecraft

## Progress

Track your improvement over multiple sessions at the same track:

- **Lap Time Trend** — Best lap time across sessions
- **Consistency Trend** — How repeatable your laps are over time
- **Corner Heatmap** — Per-corner speeds across all sessions (color-coded)
- **Box Plot** — Distribution of lap times per session
- **Milestones** — Personal bests, consistency records, corner achievements

*Requires minimum 2 sessions at the same track.*

## Equipment Profiles

Track your car setup:

1. Go to Settings → Equipment
2. Create a profile with your tire, brake, and suspension specs
3. Assign it to sessions

**Tire compound categories** affect the physics-optimal speed profile:
| Category | Example | Estimated Grip |
|----------|---------|---------------|
| Street | All-season | Low |
| Endurance 200TW | RE-71RS | Medium-high |
| Super 200TW | RT660 | High |
| 100TW | R888R | Very high |
| R-Compound | Hoosier R7 | Extremely high |
| Slick | Racing slick | Maximum |

## Sharing

Share your session with friends or your instructor:

1. Click the share button on the dashboard
2. A link is generated (valid for 7 days)
3. Anyone with the link can upload their own CSV to compare against yours

No account required for the person viewing/comparing.

## Leaderboards

Opt in to compare your corner speeds with other drivers at the same track:

1. Go to Settings → Leaderboard
2. Toggle "Participate in leaderboards"
3. View rankings per corner on the Leaderboard tab

**Corner Kings** — Best speed at each corner across all participants.

## Organizations

For HPDE groups and driving schools:

- Create an organization for your group
- Add members and assign roles (owner, instructor, student)
- Create events for track days
- Instructors can view student sessions and leave flags/notes

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `K` | Cycle through corners (deep dive) |
| `←` / `→` | Previous/next corner |
| `Esc` | Close panels |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No laps detected" | Ensure your CSV has lap timing (start/finish line set in RaceChrono) |
| "GPS quality too low" | Use a better GPS logger or check antenna placement |
| Blank charts | Refresh the page, or check if the session has clean laps |
| Upload fails | Check file is .csv format, under 50MB |
| Coaching report stuck on "generating" | Refresh after 60 seconds. The AI coach is analyzing your data |

## Supported Tracks

Currently auto-detected tracks:
- Barber Motorsports Park (16 corners, 3,662m)
- Atlanta Motorsports Park (12 corners, 3,220m)

Other tracks work with generic corner detection (heading rate analysis from GPS data). Track-specific features like landmarks and official corner numbering are available for auto-detected tracks.

## Data Privacy

- Your telemetry data is stored securely and associated with your Google account
- Sessions can be deleted at any time from the session drawer
- Shared links expire after 7 days
- Leaderboard participation is opt-in
