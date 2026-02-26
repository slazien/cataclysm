'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Cloud } from 'lucide-react';
import type { SessionWeather } from '@/lib/types';
import { useUnits } from '@/hooks/useUnits';

function MetricItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <span className="text-xs font-medium text-[var(--text-primary)]">{value}</span>
    </div>
  );
}

export function WeatherPanel({ weather }: { weather: SessionWeather }) {
  const [expanded, setExpanded] = useState(false);
  const { formatTemp } = useUnits();

  const summaryParts: string[] = [];
  if (weather.track_condition) summaryParts.push(weather.track_condition);
  if (weather.ambient_temp_c != null) summaryParts.push(formatTemp(weather.ambient_temp_c));
  const summary = summaryParts.join(' / ') || 'Unknown';

  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)]">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--bg-elevated)]"
      >
        <Cloud className="h-4 w-4 text-[var(--text-muted)]" />
        <span className="text-sm font-medium text-[var(--text-primary)]">Weather Conditions</span>
        <span className="text-sm text-[var(--text-secondary)]">{summary}</span>
        <span className="ml-auto">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-[var(--text-muted)]" />
          ) : (
            <ChevronRight className="h-4 w-4 text-[var(--text-muted)]" />
          )}
        </span>
      </button>

      {expanded && (
        <div className="grid grid-cols-2 gap-x-6 border-t border-[var(--cata-border)] px-4 py-3">
          <MetricItem label="Condition" value={weather.track_condition || '--'} />
          <MetricItem
            label="Temperature"
            value={weather.ambient_temp_c != null ? formatTemp(weather.ambient_temp_c) : '--'}
          />
          <MetricItem
            label="Humidity"
            value={weather.humidity_pct != null ? `${weather.humidity_pct}%` : '--'}
          />
          <MetricItem
            label="Wind Speed"
            value={weather.wind_speed_kmh != null ? `${weather.wind_speed_kmh} km/h` : '--'}
          />
          <MetricItem
            label="Precipitation"
            value={weather.precipitation_mm != null ? `${weather.precipitation_mm} mm` : '--'}
          />
          <MetricItem label="Source" value={weather.weather_source || '--'} />
        </div>
      )}
    </div>
  );
}
