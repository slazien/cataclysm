const SPEED_MARKER_RE = /\{\{speed:([\d.]+\+?)\}\}/g;
const SPEED_RANGE_MARKER_RE = /\{\{speed:([\d.]+)-([\d.]+)\}\}/g;
const TIME_MARKER_RE = /\{\{time:([\d.]+)\}\}/g;
const SPEED_RANGE_LEGACY_RE = /(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\s*mph/gi;
const SPEED_SINGLE_LEGACY_RE = /(\d+(?:\.\d+)?)\s*mph/gi;
const SPEED_RANGE_KMH_LEGACY_RE = /(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\s*km\/h/gi;
const SPEED_SINGLE_KMH_LEGACY_RE = /(\d+(?:\.\d+)?)\s*km\/h/gi;
const DISTANCE_M_WORD_LEGACY_RE = /(\d+(?:\.\d+)?)\s*m(?:eters?|etres?)\b/gi;
const DISTANCE_M_SINGLE_LEGACY_RE = /(\d+(?:\.\d+)?)\s*m\b(?!\s*\/)/gi;
const DISTANCE_FT_SINGLE_LEGACY_RE = /(\d+(?:\.\d+)?)\s*ft\b/gi;
const DISTANCE_FEET_WORD_LEGACY_RE = /(\d+(?:\.\d+)?)\s*feet\b/gi;
const DISTANCE_FOOT_WORD_LEGACY_RE = /(\d+(?:\.\d+)?)\s*foot\b/gi;
const TEMP_C_LEGACY_RE = /(\d+(?:\.\d+)?)\s*°C/g;
const TEMP_F_LEGACY_RE = /(\d+(?:\.\d+)?)\s*°F/g;
const PRECIP_MM_LEGACY_RE = /(\d+(?:\.\d+)?)\s*mm\b/g;
const MPH_TO_KMH = 1.60934;
const M_TO_FT = 3.28084;
const FT_TO_M = 0.3048;

function _preserve_decimals(raw: string, converted: number): string {
  const dec = raw.includes('.') ? raw.split('.')[1].length : 0;
  return converted.toFixed(dec);
}

/**
 * Resolve {{speed:N}} and {{time:N}} markers, plus legacy bare speed values.
 * Speed N is always in mph — converts to km/h when isMetric.
 * Legacy: bare "N mph" → km/h when metric; bare "N km/h" → mph when imperial.
 * Time N is always in seconds — rendered as "Ns" (no unit conversion needed).
 */
export function resolveSpeedMarkers(text: string, isMetric: boolean): string {
  // Phase 0: resolve {{time:N}} markers (unit-agnostic, always seconds)
  let result = text.replace(TIME_MARKER_RE, (_, n: string) => `${n}s`);

  // Phase 1a: range markers {{speed:N-M}} (LLM sometimes emits these)
  result = result.replace(SPEED_RANGE_MARKER_RE, (_, a: string, b: string) => {
    const mphA = parseFloat(a);
    const mphB = parseFloat(b);
    if (isNaN(mphA) || isNaN(mphB)) return `${a}-${b}`;
    if (isMetric) {
      const decA = a.includes('.') ? a.split('.')[1].length : 0;
      const decB = b.includes('.') ? b.split('.')[1].length : 0;
      return `${(mphA * MPH_TO_KMH).toFixed(decA)}-${(mphB * MPH_TO_KMH).toFixed(decB)} km/h`;
    }
    return `${a}-${b} mph`;
  });

  // Phase 1b: structured {{speed:N}} markers (may include trailing "+")
  result = result.replace(SPEED_MARKER_RE, (_, n: string) => {
    const suffix = n.endsWith('+') ? '+' : '';
    const num = n.replace(/\+$/, '');
    const mph = parseFloat(num);
    if (isNaN(mph)) return n;
    if (isMetric) {
      const dec = num.includes('.') ? num.split('.')[1].length : 0;
      return `${(mph * MPH_TO_KMH).toFixed(dec)}${suffix} km/h`;
    }
    return `${num}${suffix} mph`;
  });

  // Phase 2: legacy fallback for old cached reports and LLM drift
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
    // Metric: convert bare imperial distances back to meters.
    result = result.replace(DISTANCE_FT_SINGLE_LEGACY_RE, (_, n: string) => {
      const meters = parseFloat(n) * FT_TO_M;
      return `${_preserve_decimals(n, meters)} m`;
    });
    result = result.replace(DISTANCE_FEET_WORD_LEGACY_RE, (_, n: string) => {
      const meters = parseFloat(n) * FT_TO_M;
      return `${_preserve_decimals(n, meters)} m`;
    });
    result = result.replace(DISTANCE_FOOT_WORD_LEGACY_RE, (_, n: string) => {
      const meters = parseFloat(n) * FT_TO_M;
      return `${_preserve_decimals(n, meters)} m`;
    });
  } else {
    // Imperial: convert bare "N km/h" → mph (LLM drift or reports cached before backend fix)
    result = result.replace(SPEED_RANGE_KMH_LEGACY_RE, (_, a: string, b: string) => {
      const aMph = parseFloat(a) / MPH_TO_KMH;
      const bMph = parseFloat(b) / MPH_TO_KMH;
      return `${Math.round(aMph)}-${Math.round(bMph)} mph`;
    });
    result = result.replace(SPEED_SINGLE_KMH_LEGACY_RE, (_, n: string) => {
      const mph = parseFloat(n) / MPH_TO_KMH;
      const dec = n.includes('.') ? n.split('.')[1].length : 0;
      return `${mph.toFixed(dec)} mph`;
    });
    // Imperial: convert meter distances to feet in coaching text.
    result = result.replace(DISTANCE_M_WORD_LEGACY_RE, (_, n: string) => {
      const feet = parseFloat(n) * M_TO_FT;
      return `${_preserve_decimals(n, feet)} ft`;
    });
    result = result.replace(DISTANCE_M_SINGLE_LEGACY_RE, (_, n: string) => {
      const feet = parseFloat(n) * M_TO_FT;
      return `${_preserve_decimals(n, feet)} ft`;
    });
    // Imperial: convert bare "N°C" → °F and "Nmm" → in
    result = result.replace(TEMP_C_LEGACY_RE, (_, n: string) =>
      `${Math.round(parseFloat(n) * 9 / 5 + 32)}°F`,
    );
    result = result.replace(PRECIP_MM_LEGACY_RE, (_, n: string) =>
      `${(parseFloat(n) / 25.4).toFixed(2)}in`,
    );
  }

  // Metric: convert bare "N°F" → °C (LLM drift when it quotes imperial-only cached data)
  if (isMetric) {
    result = result.replace(TEMP_F_LEGACY_RE, (_, n: string) =>
      `${Math.round((parseFloat(n) - 32) * 5 / 9)}°C`,
    );
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

/** Extracts the title from coaching text.
 *  If text starts with **bold title**, returns the full bold portion.
 *  Otherwise falls back to extracting the first clause. */
export function extractActionTitle(text: string): string {
  // If text starts with a bold section, extract it entirely
  const boldMatch = text.match(/^(\*\*[^*]+\*\*)/);
  if (boldMatch) {
    // Strip trailing punctuation (: ; — etc.) inside the bold markers
    return boldMatch[1].replace(/([^*])[,:;\u2014\u2013-]+(\*\*)$/, '$1$2');
  }
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

/** Extracts the detail text after a bold title.
 *  Strips the leading **bold**: separator, returning just the body. */
export function extractDetailText(text: string): string {
  const boldMatch = text.match(/^\*\*[^*]+\*\*\s*[:;\u2014\u2013-]?\s*/);
  if (boldMatch) return text.slice(boldMatch[0].length).trim();
  // No bold prefix — return everything after the title clause
  const clauseMatch = text.match(/^.{10,60}?[.,;:\u2014\u2013-]\s/);
  if (clauseMatch) return text.slice(clauseMatch[0].length).trim();
  return '';
}
