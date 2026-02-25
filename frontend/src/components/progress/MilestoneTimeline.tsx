'use client';

import { useMemo, useRef, useEffect, useCallback, useState } from 'react';
import type { Milestone, TrendSessionSummary } from '@/lib/types';
import { colors, fonts } from '@/lib/design-tokens';

interface MilestoneTimelineProps {
  sessions: TrendSessionSummary[];
  milestones: Milestone[];
  className?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  pb: colors.motorsport.pb,
  consistency: colors.motorsport.optimal,
  corner_improvement: colors.motorsport.throttle,
  general: colors.motorsport.neutral,
};

const MARGINS = { top: 60, right: 24, bottom: 24, left: 24 };
const TIMELINE_Y_OFFSET = 30; // line position from top of inner area

function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? colors.motorsport.neutral;
}

export function MilestoneTimeline({ sessions, milestones, className }: MilestoneTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null);
  const [dims, setDims] = useState({ width: 0, height: 0 });

  // Build session date positions
  const sessionDates = useMemo(
    () => sessions.map((s) => new Date(s.session_date)),
    [sessions],
  );

  const xScale = useCallback(
    (date: Date) => {
      if (sessionDates.length <= 1) return MARGINS.left + (dims.width - MARGINS.left - MARGINS.right) / 2;
      const minDate = sessionDates[0].getTime();
      const maxDate = sessionDates[sessionDates.length - 1].getTime();
      const range = maxDate - minDate || 1;
      const innerWidth = dims.width - MARGINS.left - MARGINS.right;
      return MARGINS.left + ((date.getTime() - minDate) / range) * innerWidth;
    },
    [sessionDates, dims.width],
  );

  // Milestone lookup by session_date
  const milestonesByDate = useMemo(() => {
    const map = new Map<string, Milestone[]>();
    for (const m of milestones) {
      const key = m.session_date;
      const arr = map.get(key) ?? [];
      arr.push(m);
      map.set(key, arr);
    }
    return map;
  }, [milestones]);

  // Resize observer
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setDims({ width, height });
    });
    observer.observe(container);

    const rect = container.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setDims({ width: rect.width, height: rect.height });
    }

    return () => observer.disconnect();
  }, []);

  // Scale canvas for HiDPI
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = dims.width * dpr;
    canvas.height = dims.height * dpr;
    canvas.style.width = `${dims.width}px`;
    canvas.style.height = `${dims.height}px`;
    const ctx = canvas.getContext('2d');
    if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }, [dims]);

  // Draw
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || dims.width <= 0 || sessions.length === 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, dims.width, dims.height);

    const lineY = MARGINS.top + TIMELINE_Y_OFFSET;
    const innerWidth = dims.width - MARGINS.left - MARGINS.right;

    // Timeline line
    ctx.strokeStyle = colors.axis;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(MARGINS.left, lineY);
    ctx.lineTo(MARGINS.left + innerWidth, lineY);
    ctx.stroke();

    // Session circles
    for (let i = 0; i < sessions.length; i++) {
      const x = xScale(sessionDates[i]);
      const hasMilestone = milestonesByDate.has(sessions[i].session_date);

      ctx.beginPath();
      ctx.arc(x, lineY, hasMilestone ? 6 : 4, 0, Math.PI * 2);
      ctx.fillStyle = hasMilestone ? colors.motorsport.pb : colors.bg.elevated;
      ctx.fill();
      ctx.strokeStyle = hasMilestone ? colors.motorsport.pb : colors.axis;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Date label below
      ctx.fillStyle = colors.text.muted;
      ctx.font = `10px ${fonts.mono}`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const dateLabel = sessionDates[i].toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      });
      ctx.fillText(dateLabel, x, lineY + 12);
    }

    // Milestone pins above timeline
    for (const [dateStr, ms] of milestonesByDate.entries()) {
      const matchSession = sessions.find((s) => s.session_date === dateStr);
      if (!matchSession) continue;
      const x = xScale(new Date(dateStr));

      for (let j = 0; j < ms.length; j++) {
        const m = ms[j];
        const pinY = lineY - 18 - j * 22;
        const categoryColor = getCategoryColor(m.category);

        // Pin line
        ctx.strokeStyle = categoryColor;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 2]);
        ctx.beginPath();
        ctx.moveTo(x, lineY - 6);
        ctx.lineTo(x, pinY + 6);
        ctx.stroke();
        ctx.setLineDash([]);

        // Flag/badge
        ctx.fillStyle = categoryColor;
        ctx.beginPath();
        ctx.arc(x, pinY, 5, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = colors.text.primary;
        ctx.font = `10px ${fonts.sans}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        const label =
          m.description.length > 30 ? m.description.slice(0, 28) + '...' : m.description;
        ctx.fillText(label, x, pinY - 8);
      }
    }
  }, [sessions, milestones, sessionDates, milestonesByDate, xScale, dims]);

  // Hover for tooltip
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas || sessions.length === 0) return;
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;
      const lineY = MARGINS.top + TIMELINE_Y_OFFSET;

      // Check milestones first
      for (const [dateStr, ms] of milestonesByDate.entries()) {
        const x = xScale(new Date(dateStr));
        for (let j = 0; j < ms.length; j++) {
          const pinY = lineY - 18 - j * 22;
          const dx = mouseX - x;
          const dy = mouseY - pinY;
          if (dx * dx + dy * dy < 100) {
            setTooltip({ x: mouseX, y: mouseY - 20, text: ms[j].description });
            return;
          }
        }
      }

      // Check session circles
      for (let i = 0; i < sessions.length; i++) {
        const x = xScale(sessionDates[i]);
        const dx = mouseX - x;
        const dy = mouseY - lineY;
        if (dx * dx + dy * dy < 64) {
          const s = sessions[i];
          setTooltip({
            x: mouseX,
            y: mouseY - 20,
            text: `${s.session_date} — Best: ${s.best_lap_time_s.toFixed(2)}s, ${s.n_laps} laps`,
          });
          return;
        }
      }

      setTooltip(null);
    },
    [sessions, sessionDates, milestonesByDate, xScale],
  );

  const handleMouseLeave = useCallback(() => setTooltip(null), []);

  if (sessions.length === 0) {
    return (
      <div className={className}>
        <p className="py-8 text-center text-sm text-[var(--text-muted)]">
          No sessions to display
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`relative h-[160px] w-full ${className ?? ''}`}>
      <canvas
        ref={canvasRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 max-w-[240px] rounded bg-[var(--bg-overlay)] px-2 py-1 text-xs text-[var(--text-primary)] shadow-lg"
          style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
