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

/** Extracts a short action phrase from long coaching text.
 *  Takes the first clause (before a comma, period, semicolon, colon, or dash) and caps it. */
export function extractActionTitle(text: string): string {
  // Try to grab first short clause
  const match = text.match(/^(.{10,60}?)[.,;:\u2014\u2013-]\s/);
  if (match) return match[1].trim();
  // Fallback: first N words up to ~50 chars
  const words = text.split(/\s+/);
  let result = '';
  for (const w of words) {
    if ((result + ' ' + w).trim().length > 50) break;
    result = (result + ' ' + w).trim();
  }
  return result || text.slice(0, 50);
}
