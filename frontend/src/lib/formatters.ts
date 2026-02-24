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
