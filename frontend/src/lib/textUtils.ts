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
