/** Normalize a score that may be in 0-1 or 0-100 range to 0-100. */
export function normalizeScore(raw: number): number {
  return raw <= 1 ? raw * 100 : raw;
}

export function formatLapTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toFixed(3).padStart(6, "0")}`;
}

export function formatDelta(seconds: number): string {
  const sign = seconds >= 0 ? "+" : "";
  return `${sign}${seconds.toFixed(3)}s`;
}

export function formatSpeed(mph: number): string {
  return `${mph.toFixed(1)} mph`;
}

/** Format seconds as M:SS.s or SS.SSs for canvas chart labels */
export function formatTimeShort(seconds: number): string {
  const min = Math.floor(seconds / 60);
  const sec = seconds % 60;
  return min > 0 ? `${min}:${sec.toFixed(1).padStart(4, '0')}` : `${sec.toFixed(2)}s`;
}

/**
 * Parse a session date string from the backend.
 * Primary format: ISO 8601 ("2026-03-21T12:31:00Z").
 * Fallback: legacy DD/MM/YYYY HH:MM for cached responses.
 */
export function parseSessionDate(dateStr: string): Date {
  // Try ISO first (new format)
  const iso = new Date(dateStr);
  if (!isNaN(iso.getTime()) && dateStr.includes('-')) return iso;

  // Fallback: DD/MM/YYYY HH:MM (legacy cached responses)
  const ddmm = dateStr.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/);
  if (ddmm) {
    const [, day, month, year, hour, min] = ddmm;
    return new Date(+year, +month - 1, +day, +(hour ?? 0), +(min ?? 0));
  }

  return new Date(dateStr);
}

/**
 * Format an ISO session date for display when session_date_local is unavailable.
 * Returns a UTC-based fallback like "Mar 21, 2026 · 12:31 PM UTC".
 */
export function formatSessionDate(isoStr: string): string {
  if (!isoStr) return '—';
  const d = parseSessionDate(isoStr);
  if (isNaN(d.getTime())) return '—';
  const month = d.toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' });
  const day = d.getUTCDate();
  const year = d.getUTCFullYear();
  const hours = d.getUTCHours();
  const minutes = d.getUTCMinutes().toString().padStart(2, '0');
  const ampm = hours >= 12 ? 'PM' : 'AM';
  const h12 = hours % 12 || 12;
  return `${month} ${day}, ${year} · ${h12}:${minutes} ${ampm} UTC`;
}
