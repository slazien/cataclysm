'use client';

import { useState, useRef, useEffect } from 'react';
import { AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react';
import { useDegradation } from '@/hooks/useAnalysis';
import { colors } from '@/lib/design-tokens';
import type { DegradationEvent } from '@/lib/types';

const SEVERITY_COLORS: Record<string, string> = {
  mild: '#eab308',
  moderate: '#f97316',
  severe: '#ef4444',
};

const SEVERITY_BG: Record<string, string> = {
  mild: 'rgba(234, 179, 8, 0.1)',
  moderate: 'rgba(249, 115, 22, 0.1)',
  severe: 'rgba(239, 68, 68, 0.1)',
};

function Sparkline({ values, color, width = 80, height = 24 }: {
  values: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || values.length < 2) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const pad = 2;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    values.forEach((v, i) => {
      const x = pad + (i / (values.length - 1)) * (width - 2 * pad);
      const y = pad + (1 - (v - min) / range) * (height - 2 * pad);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }, [values, color, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height }}
      className="flex-shrink-0"
    />
  );
}

function EventCard({ event }: { event: DegradationEvent }) {
  const [expanded, setExpanded] = useState(false);
  const severityColor = SEVERITY_COLORS[event.severity] ?? colors.text.muted;
  const severityBg = SEVERITY_BG[event.severity] ?? 'transparent';

  const metricLabel = event.metric === 'brake_fade' ? 'Brake Fade' : 'Tire Degradation';
  const Icon = expanded ? ChevronUp : ChevronDown;

  return (
    <div
      className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-3"
      style={{ borderLeftColor: severityColor, borderLeftWidth: 3 }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3"
      >
        {/* Severity badge */}
        <span
          className="rounded px-1.5 py-0.5 text-[10px] font-bold uppercase"
          style={{ color: severityColor, backgroundColor: severityBg }}
        >
          {event.severity}
        </span>

        {/* Info */}
        <div className="flex-1 text-left">
          <div className="text-xs font-medium text-[var(--text-primary)]">
            T{event.corner_number} — {metricLabel}
          </div>
        </div>

        {/* Sparkline */}
        <Sparkline values={event.values} color={severityColor} />

        <Icon size={14} className="text-[var(--text-muted)]" />
      </button>

      {expanded && (
        <div className="mt-2 border-t border-[var(--cata-border)] pt-2 text-xs text-[var(--text-secondary)]">
          <p>{event.description}</p>
          <div className="mt-1 flex gap-4 text-[10px] text-[var(--text-muted)]">
            <span>Laps {event.start_lap}–{event.end_lap}</span>
            <span>R² = {event.r_squared.toFixed(2)}</span>
            <span>Slope: {event.slope.toFixed(4)}/lap</span>
          </div>
        </div>
      )}
    </div>
  );
}

interface DegradationAlertsProps {
  sessionId: string;
}

export function DegradationAlerts({ sessionId }: DegradationAlertsProps) {
  const { data } = useDegradation(sessionId);

  // Don't render anything if no degradation detected
  if (!data || data.events.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className="text-[var(--text-muted)]" />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
          Equipment Degradation Detected
        </h3>
      </div>
      <div className="space-y-2">
        {data.events.map((event, i) => (
          <EventCard key={`${event.corner_number}-${event.metric}-${i}`} event={event} />
        ))}
      </div>
    </div>
  );
}
