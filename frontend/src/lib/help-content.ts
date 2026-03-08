/**
 * Centralized help text for contextual (?) tooltips throughout the app.
 * Keyed by `{type}.{kebab-name}` convention.
 *
 * Unlike glossary.ts (motorsport terminology, skill-level-aware),
 * these entries explain UI elements, charts, and metrics.
 */

export const helpContent: Record<string, string> = {
  // ── Metrics ──────────────────────────────────────────────
  'metric.best-lap':
    'Your fastest lap time in this session. Highlighted in purple on the lap times chart.',
  'metric.top3-avg':
    'Average of your 3 fastest laps. A more stable measure of your true pace than a single lap.',
  'metric.session-avg':
    'Average lap time across all laps in the session, including slower ones.',
  'metric.consistency':
    'How repeatable your lap times are. Higher % = less variation between laps. Consistent drivers extract more from every session.',
  'metric.clean-laps':
    'Laps without significant off-track excursions or anomalies. More clean laps = better data for analysis.',
  'metric.top-speed':
    'Highest speed recorded at any point during the session.',
  'metric.optimal-lap':
    "What's physically achievable for your car and tires on this track — not a best-sectors average. A physics simulation uses your car's weight, tire compound, and the G-forces you actually generated to set a target unique to your equipment and this session. The delta is realistic, actionable time to find.",
  'metric.session-score':
    'Overall session rating (0-100) combining available components: Consistency (40%), Pace vs. the ideal-lap pace reference (30%), and Corner grades (30%). If one component is missing or invalid, the remaining weights are renormalized.',
  'metric.sessions':
    'Total number of sessions analyzed. More sessions = more reliable trend data.',
  'metric.pace-spread':
    'On this screen, this metric is your Top 3 Average minus your Best Lap. Smaller gap = your fast pace is repeatable, not just a one-off peak.',

  // ── Charts ───────────────────────────────────────────────
  'chart.speed-trace':
    'Speed vs. distance around the lap. Compare two laps to see where you gain or lose time. Steeper drops = harder braking.',
  'chart.delta-t':
    "Running time gap between two laps, accumulated around the track. A dropping line (green) means gaining time; rising (red) means losing it. The steepest moves pinpoint exactly where the laps diverge — these are your highest-leverage corners.",
  'chart.brake-throttle':
    'Brake and throttle inputs plotted over distance. Look for smooth transitions and consistent brake application points.',
  'chart.driving-line':
    'Your racing line shown on the track map. Compare two laps to see line variation — consistent lines through corners are key.',
  'chart.gg-diagram':
    "Lateral vs. longitudinal G-forces plotted together — the traction circle. Your tires have a fixed total grip budget: braking, cornering, and accelerating all share it. A fuller shape means you're using more of that budget. Gaps in the upper-left (braking+turning) are the most common time loss.",
  'metric.grip-utilization':
    "How much of your tire's total grip envelope you're using — combining braking, cornering, and acceleration forces. 100% means you're at the physical limit everywhere. Gaps show where grip is left unused, usually the highest-opportunity areas.",
  'chart.corner-speed-overlay':
    'Speed traces through a single corner across multiple laps, aligned by distance. Shows how consistently you drive each corner.',
  'chart.brake-consistency':
    'Brake pressure traces overlaid for the same corner across laps. Consistent braking = consistent corner entry.',
  'chart.speed-gap':
    "How much speed you're carrying through each corner compared to what your car and tires could physically achieve. Each bar converts directly to time — the corner with the largest gap is your biggest single opportunity.",
  'chart.lap-times-bar':
    'Bar chart of all lap times. Purple = personal best, blue = clean laps, gray = unclean. Dashed lines show PB and average.',
  'chart.time-gained':
    'Time left on the table per corner — the gap between your average and best through each section. Focus practice on the biggest bars.',
  'chart.skill-radar':
    'Five-dimension skill profile based on corner grades: Braking, Trail Braking, Minimum Speed, Throttle Application, and Line Consistency.',
  'chart.lap-time-trend':
    'Lap time progression across sessions. Downward trend = you\'re getting faster. Dots are session bests, line is the trend.',
  'chart.consistency-trend':
    'Consistency score over time. Upward trend = you\'re becoming more repeatable. Consistency often improves before raw pace.',
  'chart.corner-heatmap':
    'Color-coded grid of corner grades across sessions. Green = strong, red = needs work. Spot patterns — some corners may consistently lag.',
  'chart.session-boxplot':
    'Box plot showing lap time distribution per session. The box spans the middle 50% of laps; whiskers show the full range. Tighter boxes = more consistent.',
  'chart.corner-sparklines':
    'Mini trend lines for each corner\'s grade over time. Quick visual to see which corners are improving or declining.',
  'chart.milestone-timeline':
    'Key achievements and milestones across your sessions. Tracks when you hit personal bests and consistency targets.',
  'chart.skill-radar-evolution':
    'How your skill profile has changed across sessions. Faded shapes are historical — watch the profile expand as you improve.',
  'chart.delta-map':
    'Track map colored by time difference between sessions. Green = gaining time, red = losing time. Hotspots show where the biggest differences occur.',

  // ── Grades ───────────────────────────────────────────────
  'grade.braking':
    'How well you brake for each corner: consistency of brake point, peak brake force, and release technique. A = excellent, F = needs significant work.',
  'grade.trail-braking':
    'Your ability to blend braking into the turn-in phase. Good trail braking loads the front tires for better grip at corner entry.',
  'grade.min-speed':
    "How close you got to the maximum speed the physics model says is achievable at this corner's apex. A = at the limit. Lower grades mean you braked too early or were too cautious through the middle — this is the most direct link between technique and your optimal lap time.",
  'grade.throttle':
    'How early and smoothly you get back to full throttle on corner exit. Earlier throttle commit = more speed down the straight.',

  // ── Sections ─────────────────────────────────────────────
  'section.top-priorities':
    "The corners where your gap to the physics-optimal is largest, ranked by opportunity. Fixing the top priority first is how professionals build a faster lap one corner at a time. Time figures are physics-based estimates of potential gain.",
  'section.corner-grades':
    'Letter grades (A-F) for each corner across four dimensions. Grades are based on your telemetry compared to optimal technique patterns.',
  'section.score-breakdown':
    'How the session score is calculated: Consistency (40%) measures lap time repeatability, Pace (30%) compares your best lap to the ideal-lap pace reference, and Corner Grades (30%) average your technique scores. Missing components are re-weighted rather than treated as zero.',
  'section.session-metrics':
    'Key performance indicators summarizing this session. Compare across sessions on the Progress tab.',
  'section.track-guide':
    'A briefing on this track\'s layout, key corners, and notable features. Shown for novice drivers to build familiarity before diving into telemetry.',
};
