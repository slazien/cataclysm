'use client';

import { useRef, useState, useEffect, useCallback } from 'react';
import { X, ChevronLeft, ChevronRight, Sparkles, Trophy, Clock, MapPin, Gauge } from 'lucide-react';
import { useWrapped } from '@/hooks/useWrapped';
import type { WrappedData } from '@/lib/types';

/* ── Personality icon mapping ───────────────────────── */
const PERSONALITY_COLORS: Record<string, string> = {
  'The Late Braker': '#ef4444',
  'The Smooth Operator': '#a855f7',
  'The Throttle Master': '#22c55e',
  'The Machine': '#3b82f6',
  'The Track Day Warrior': '#f59e0b',
};

/* ── Individual card components ─────────────────────── */

function IntroCard({ data }: { data: WrappedData }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-8 text-center">
      <Sparkles className="h-16 w-16 text-[var(--cata-accent)]" />
      <h2 className="text-5xl font-bold text-white">{data.year}</h2>
      <p className="text-xl text-[var(--text-secondary)]">Your Year in Review</p>
      <p className="text-sm text-[var(--text-muted)]">
        {data.total_sessions} session{data.total_sessions !== 1 ? 's' : ''} analyzed
      </p>
    </div>
  );
}

function StatsCard({ data }: { data: WrappedData }) {
  const stats = [
    { icon: Trophy, label: 'Total Laps', value: data.total_laps.toLocaleString(), color: '#f59e0b' },
    { icon: MapPin, label: 'Tracks Visited', value: String(data.tracks_visited.length), color: '#3b82f6' },
    { icon: Clock, label: 'Track Time', value: `${data.total_track_time_hours.toFixed(1)}h`, color: '#22c55e' },
    { icon: Gauge, label: 'Distance', value: `${data.total_distance_km.toFixed(0)} km`, color: '#a855f7' },
  ];

  return (
    <div className="flex h-full flex-col items-center justify-center gap-8 p-8">
      <h3 className="text-2xl font-semibold text-white">By the Numbers</h3>
      <div className="grid grid-cols-2 gap-6">
        {stats.map((s) => (
          <div key={s.label} className="flex flex-col items-center gap-2">
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl"
              style={{ backgroundColor: `${s.color}20` }}
            >
              <s.icon className="h-7 w-7" style={{ color: s.color }} />
            </div>
            <span className="text-2xl font-bold text-white">{s.value}</span>
            <span className="text-xs text-[var(--text-muted)]">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ImprovementCard({ data }: { data: WrappedData }) {
  if (!data.biggest_improvement_track || !data.biggest_improvement_s) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
        <h3 className="text-2xl font-semibold text-white">Biggest Improvement</h3>
        <p className="text-[var(--text-muted)]">
          Visit the same track twice to track your improvement!
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-8 text-center">
      <h3 className="text-2xl font-semibold text-white">Biggest Improvement</h3>
      <div className="rounded-2xl bg-[var(--bg-elevated)] p-6">
        <p className="text-sm text-[var(--text-muted)]">{data.biggest_improvement_track}</p>
        <p className="mt-2 text-4xl font-bold text-[#22c55e]">
          -{data.biggest_improvement_s.toFixed(2)}s
        </p>
        <p className="mt-1 text-xs text-[var(--text-muted)]">faster from first to last session</p>
      </div>
      <div className="text-sm text-[var(--text-secondary)]">
        Best consistency: {data.best_consistency_score.toFixed(0)}%
      </div>
    </div>
  );
}

function PersonalityCard({ data }: { data: WrappedData }) {
  const color = PERSONALITY_COLORS[data.personality] ?? '#f59e0b';

  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 p-8 text-center">
      <h3 className="text-2xl font-semibold text-white">Your Driving Personality</h3>
      <div
        className="rounded-2xl border-2 px-8 py-6"
        style={{ borderColor: color, backgroundColor: `${color}10` }}
      >
        <p className="text-3xl font-bold" style={{ color }}>
          {data.personality}
        </p>
      </div>
      <p className="max-w-xs text-sm text-[var(--text-secondary)]">
        {data.personality_description}
      </p>
      {data.tracks_visited.length > 0 && (
        <div className="mt-2 text-xs text-[var(--text-muted)]">
          Tracks: {data.tracks_visited.join(', ')}
        </div>
      )}
    </div>
  );
}

/* ── Main SeasonWrapped modal ───────────────────────── */

interface SeasonWrappedProps {
  open: boolean;
  onClose: () => void;
}

export function SeasonWrapped({ open, onClose }: SeasonWrappedProps) {
  const year = new Date().getFullYear();
  const { data, isLoading, error } = useWrapped(year, open);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [activeSlide, setActiveSlide] = useState(0);
  const totalSlides = 4;

  // Track scroll position for dot indicators
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const handleScroll = () => {
      const idx = Math.round(el.scrollLeft / el.clientWidth);
      setActiveSlide(idx);
    };
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, [data]);

  // Reset scroll on open
  useEffect(() => {
    if (open) {
      setActiveSlide(0);
      scrollRef.current?.scrollTo({ left: 0 });
    }
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  const scrollTo = useCallback((idx: number) => {
    scrollRef.current?.scrollTo({
      left: idx * (scrollRef.current?.clientWidth ?? 0),
      behavior: 'smooth',
    });
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Card container — phone-like aspect ratio */}
      <div className="relative h-[min(85vh,680px)] w-[min(90vw,380px)] overflow-hidden rounded-3xl bg-[var(--bg-surface)] shadow-2xl">
        {/* Close button */}
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-10 rounded-full bg-black/40 p-1.5 text-white/70 transition hover:bg-black/60 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>

        {isLoading && (
          <div className="flex h-full items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--cata-accent)] border-t-transparent" />
          </div>
        )}

        {error && (
          <div className="flex h-full items-center justify-center p-8 text-center">
            <p className="text-[var(--text-muted)]">Could not load your year in review.</p>
          </div>
        )}

        {data && (
          <>
            {/* Scrollable card area */}
            <div
              ref={scrollRef}
              className="flex h-full snap-x snap-mandatory overflow-x-auto scrollbar-hide"
              style={{ scrollbarWidth: 'none' }}
            >
              {[IntroCard, StatsCard, ImprovementCard, PersonalityCard].map((Card, i) => (
                <div key={i} className="h-full w-full flex-shrink-0 snap-center">
                  <Card data={data} />
                </div>
              ))}
            </div>

            {/* Dot indicators */}
            <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 gap-2">
              {Array.from({ length: totalSlides }).map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => scrollTo(i)}
                  className={`h-2 rounded-full transition-all ${
                    i === activeSlide
                      ? 'w-6 bg-[var(--cata-accent)]'
                      : 'w-2 bg-white/30'
                  }`}
                />
              ))}
            </div>

            {/* Arrow navigation */}
            {activeSlide > 0 && (
              <button
                type="button"
                onClick={() => scrollTo(activeSlide - 1)}
                className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-1 text-white/70 hover:bg-black/60"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
            )}
            {activeSlide < totalSlides - 1 && (
              <button
                type="button"
                onClick={() => scrollTo(activeSlide + 1)}
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/40 p-1 text-white/70 hover:bg-black/60"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
