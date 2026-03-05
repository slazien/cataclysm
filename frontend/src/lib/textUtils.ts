const SPEED_MARKER_RE = /\{\{speed:([\d.]+)\}\}/g;
const SPEED_RANGE_LEGACY_RE = /(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\s*mph/gi;
const SPEED_SINGLE_LEGACY_RE = /(\d+(?:\.\d+)?)\s*mph/gi;
const MPH_TO_KMH = 1.60934;

/**
 * Resolve {{speed:N}} markers and legacy bare "N mph" values in coaching text.
 * N is always in mph. When isMetric is true, converts to km/h.
 */
export function resolveSpeedMarkers(text: string, isMetric: boolean): string {
  // Phase 1: structured {{speed:N}} markers
  let result = text.replace(SPEED_MARKER_RE, (_, n: string) => {
    const mph = parseFloat(n);
    if (isNaN(mph)) return n;
    if (isMetric) {
      const dec = n.includes('.') ? n.split('.')[1].length : 0;
      return `${(mph * MPH_TO_KMH).toFixed(dec)} km/h`;
    }
    return `${n} mph`;
  });

  // Phase 2: legacy fallback for old cached reports (bare "N mph")
  if (isMetric) {
    // Ranges first ("2-3 mph"), then singles ("42 mph")
    result = result.replace(SPEED_RANGE_LEGACY_RE, (_, a: string, b: string) => {
      const aK = parseFloat(a) * MPH_TO_KMH;
      const bK = parseFloat(b) * MPH_TO_KMH;
      return `${Math.round(aK)}-${Math.round(bK)} km/h`;
    });
    result = result.replace(SPEED_SINGLE_LEGACY_RE, (_, n: string) => {
      const kmh = parseFloat(n) * MPH_TO_KMH;
      const dec = n.includes('.') ? n.split('.')[1].length : 0;
      return `${kmh.toFixed(dec)} km/h`;
    });
  }

  return result;
}

/**
 * Insert paragraph breaks into coaching text that was generated as a single
 * long string (older cached reports). New reports already contain \n\n breaks
 * from the updated prompt, so this is a no-op for those.
 *
 * Splits before structured markers like "Lap 1-2:", "Goal:", "Early laps",
 * "Focus on", "This decouples", etc. that indicate logical paragraph boundaries.
 */
export function formatCoachingText(text: string): string {
  // Already has paragraph breaks — leave it alone
  if (text.includes('\n\n')) return text;

  // Patterns that indicate a new paragraph should start before them.
  // Each regex matches ". <marker>" and inserts \n\n before the marker.
  const breakPatterns = [
    // Drill step markers: "Lap 1-2:", "Laps 3-4:", "On laps 1-2"
    /(?<=\.)\s+(?=(?:On\s+)?Laps?\s+\d)/g,
    // Measurement/target sections
    /(?<=\.)\s+(?=Measure:|Target:|Goal:|Result:)/g,
    // Evidence sentences: "Early laps", "Best laps", "Worst laps", "Your best"
    /(?<=\.)\s+(?=(?:Early|Best|Worst|Your best|Your worst|The best|The worst)\s+laps?\b)/g,
    // Conclusion/explanation sentences starting with "This"
    /(?<=\.)\s+(?=This\s+(?!is\b)\w)/g,
    // Section headers with colon
    /(?<=\.)\s+(?=Focus:|Setup:|Execution:|Key:|Note:)/g,
    // Action instructions without colon
    /(?<=\.)\s+(?=(?:Focus on|Deliberately|Practice|Once|Start with|Begin)\s)/g,
    // Numbered steps: "1.", "2.", "3." at logical boundaries
    /(?<=\.)\s+(?=\d+\.\s+[A-Z])/g,
    // Throttle/brake summary conclusions
    /(?<=\.)\s+(?=Throttle\s+is\b)/g,
  ];

  let result = text;
  for (const pattern of breakPatterns) {
    result = result.replace(pattern, '\n\n');
  }

  return result;
}

/** Close any unclosed markdown bold/italic markers so truncated text renders cleanly. */
function closeMarkdown(s: string): string {
  // Count ** pairs (bold)
  const boldCount = (s.match(/\*\*/g) || []).length;
  if (boldCount % 2 !== 0) s += '**';
  // Count remaining lone * (italic) after replacing ** with placeholder
  const withoutBold = s.replace(/\*\*/g, '');
  const italicCount = (withoutBold.match(/\*/g) || []).length;
  if (italicCount % 2 !== 0) s += '*';
  return s;
}

/** Extracts a short action phrase from long coaching text.
 *  Takes the first clause (before a comma, period, semicolon, colon, or dash) and caps it. */
export function extractActionTitle(text: string): string {
  // Try to grab first short clause
  const match = text.match(/^(.{10,60}?)[.,;:\u2014\u2013-]\s/);
  if (match) return closeMarkdown(match[1].trim());
  // Fallback: first N words up to ~50 chars
  const words = text.split(/\s+/);
  let result = '';
  for (const w of words) {
    if ((result + ' ' + w).trim().length > 50) break;
    result = (result + ' ' + w).trim();
  }
  return closeMarkdown(result || text.slice(0, 50));
}
