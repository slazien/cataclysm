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
 * Backend format: "DD/MM/YYYY HH:MM" — JS Date constructor doesn't parse this.
 */
export function parseSessionDate(dateStr: string): Date {
  const [datePart, timePart] = dateStr.split(' ');
  const [day, month, year] = datePart.split('/');
  return new Date(`${year}-${month}-${day}T${timePart ?? '00:00'}`);
}
