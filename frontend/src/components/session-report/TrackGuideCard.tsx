'use client';

import { useState, useEffect } from 'react';
import {
  MapPin,
  Ruler,
  Mountain,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  ArrowLeft,
  AlertTriangle,
  Eye,
  Building2,
  Shield,
  Square,
  Flag,
  Navigation,
} from 'lucide-react';
import { useTrackGuide } from '@/hooks/useTrackGuide';
import { InfoTooltip } from '@/components/shared/InfoTooltip';
import type { KeyCorner, TrackGuideCorner, TrackGuideLandmark } from '@/lib/types';

interface TrackGuideCardProps {
  sessionId: string;
}

const STORAGE_KEY_PREFIX = 'track-briefing-seen:';

function useHasSeen(sessionId: string, dataLoaded: boolean) {
  const key = `${STORAGE_KEY_PREFIX}${sessionId}`;
  const [seen, setSeen] = useState(true); // Default collapsed until check

  // Read localStorage on mount to determine initial state
  useEffect(() => {
    const stored = localStorage.getItem(key);
    setSeen(stored === 'true');
  }, [key]);

  // Only mark as "seen" after data has loaded and the card can render
  useEffect(() => {
    if (dataLoaded) {
      localStorage.setItem(key, 'true');
    }
  }, [key, dataLoaded]);

  return seen;
}

function DirectionArrow({ direction }: { direction: string | null }) {
  if (direction === 'left') return <ArrowLeft className="h-3.5 w-3.5 text-[var(--text-secondary)]" />;
  if (direction === 'right') return <ArrowRight className="h-3.5 w-3.5 text-[var(--text-secondary)]" />;
  return null;
}

function CollapsibleSection({
  title,
  defaultOpen,
  children,
  count,
}: {
  title: string;
  defaultOpen: boolean;
  children: React.ReactNode;
  count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between py-2 text-left"
      >
        <span className="font-[family-name:var(--font-display)] text-xs font-medium uppercase tracking-wider text-[var(--text-secondary)]">
          {title}
          {count !== undefined && (
            <span className="ml-1.5 text-[var(--text-secondary)]">({count})</span>
          )}
        </span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
        ) : (
          <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
        )}
      </button>
      {open && <div className="pb-2">{children}</div>}
    </div>
  );
}

function StatCard({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-4 w-4 shrink-0 text-[var(--cata-accent)]" />
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
        <p className="truncate text-sm font-medium text-[var(--text-primary)]">{value}</p>
      </div>
    </div>
  );
}

function KeyCornerCard({ corner }: { corner: KeyCorner }) {
  return (
    <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-3">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--cata-accent)]/15 text-xs font-bold text-[var(--cata-accent)]">
          {corner.number}
        </span>
        <span className="font-medium text-sm text-[var(--text-primary)]">{corner.name}</span>
        <DirectionArrow direction={corner.direction} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <span className="inline-flex items-center gap-1 rounded-full bg-[var(--cata-accent)]/10 px-2 py-0.5 text-[10px] font-semibold text-[var(--cata-accent)]">
          Exit speed critical
        </span>
        <span className="text-[10px] text-[var(--text-secondary)]">
          {Math.round(corner.straight_after_m)}m straight after
        </span>
      </div>

      {corner.blind && (
        <div className="mt-1.5 flex items-center gap-1 text-[10px] text-amber-400">
          <AlertTriangle className="h-3 w-3" />
          <span>Blind</span>
        </div>
      )}

      {corner.camber && corner.camber !== 'positive' && (
        <div className="mt-1 flex items-center gap-1 text-[10px] text-amber-400">
          <AlertTriangle className="h-3 w-3" />
          <span className="capitalize">{corner.camber}</span>
        </div>
      )}

      {corner.coaching_notes && (
        <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
          {corner.coaching_notes}
        </p>
      )}
    </div>
  );
}

function CornerRow({ corner }: { corner: TrackGuideCorner }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <tr
        className="cursor-pointer border-b border-[var(--cata-border)]/50 hover:bg-[var(--bg-surface)]"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="whitespace-nowrap py-2 pl-2 pr-3 text-xs font-medium text-[var(--text-primary)]">
          T{corner.number}
        </td>
        <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--text-secondary)]">
          <DirectionArrow direction={corner.direction} />
        </td>
        <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--text-secondary)] capitalize">
          {corner.corner_type ?? '—'}
        </td>
        <td className="whitespace-nowrap py-2 pr-3 text-xs text-[var(--text-secondary)] capitalize">
          {corner.elevation_trend ?? '—'}
        </td>
        <td className="whitespace-nowrap py-2 pr-2 text-xs">
          <div className="flex items-center gap-1">
            {corner.blind && (
              <span className="inline-flex items-center gap-0.5 text-amber-400" title="Blind">
                <Eye className="h-3 w-3" />
              </span>
            )}
            {corner.camber && corner.camber !== 'positive' && (
              <span className="text-amber-400 capitalize" title={corner.camber}>
                ⚠
              </span>
            )}
          </div>
        </td>
      </tr>
      {expanded && corner.coaching_notes && (
        <tr className="border-b border-[var(--cata-border)]/50 bg-[var(--bg-surface)]">
          <td colSpan={5} className="px-2 py-2 text-xs leading-relaxed text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--text-primary)]">T{corner.number} {corner.name}:</span>{' '}
            {corner.coaching_notes}
          </td>
        </tr>
      )}
    </>
  );
}

function LandmarkIcon({ type }: { type: string }) {
  switch (type) {
    case 'brake_board':
      return <Square className="h-3.5 w-3.5 text-red-400" />;
    case 'structure':
      return <Building2 className="h-3.5 w-3.5 text-[var(--text-secondary)]" />;
    case 'barrier':
      return <Shield className="h-3.5 w-3.5 text-amber-400" />;
    case 'curbing':
      return <Flag className="h-3.5 w-3.5 text-[var(--text-secondary)]" />;
    case 'sign':
      return <Navigation className="h-3.5 w-3.5 text-[var(--text-secondary)]" />;
    default:
      return <MapPin className="h-3.5 w-3.5 text-[var(--text-secondary)]" />;
  }
}

function LandmarkList({ landmarks }: { landmarks: TrackGuideLandmark[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? landmarks : landmarks.slice(0, 5);
  const remaining = landmarks.length - 5;

  return (
    <div className="space-y-1.5">
      {visible.map((lm, i) => (
        <div key={i} className="flex items-start gap-2 text-xs">
          <LandmarkIcon type={lm.landmark_type} />
          <div className="min-w-0">
            <span className="font-medium text-[var(--text-primary)]">{lm.name}</span>
            <span className="ml-1.5 text-[var(--text-secondary)]">{Math.round(lm.distance_m)}m</span>
            {lm.description && (
              <span className="ml-1 text-[var(--text-secondary)]">— {lm.description}</span>
            )}
          </div>
        </div>
      ))}
      {!showAll && remaining > 0 && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="text-xs text-[var(--cata-accent)] hover:underline"
        >
          Show {remaining} more
        </button>
      )}
    </div>
  );
}

function formatLength(m: number | null): string {
  if (m == null) return '—';
  if (m >= 1000) return `${(m / 1000).toFixed(2)} km`;
  return `${Math.round(m)} m`;
}

export function TrackGuideCard({ sessionId }: TrackGuideCardProps) {
  const { data: guide, isError } = useTrackGuide(sessionId);
  const hasSeen = useHasSeen(sessionId, !!guide);
  const [collapsed, setCollapsed] = useState(true);

  // Once data loads, decide initial collapsed state
  useEffect(() => {
    if (guide) {
      setCollapsed(hasSeen);
    }
  }, [guide, hasSeen]);

  if (!guide || isError) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--cata-accent)]/20 bg-[var(--bg-surface)]">
      {/* Header — always visible */}
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        aria-expanded={!collapsed}
        className="flex w-full items-center justify-between p-4"
      >
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-[var(--cata-accent)]" />
          <span className="font-[family-name:var(--font-display)] text-sm font-semibold text-[var(--text-primary)]">
            Track Briefing
          </span>
          <InfoTooltip helpKey="section.track-guide" />
        </div>
        <div className="flex items-center gap-2">
          {collapsed && (
            <span className="text-xs text-[var(--text-secondary)]">
              {guide.track_name} · {guide.n_corners} turns
            </span>
          )}
          {collapsed ? (
            <ChevronDown className="h-4 w-4 text-[var(--text-secondary)]" />
          ) : (
            <ChevronUp className="h-4 w-4 text-[var(--text-secondary)]" />
          )}
        </div>
      </button>

      {!collapsed && (
        <div className="space-y-4 border-t border-[var(--cata-border)]/50 px-4 pb-4 pt-3">
          {/* Section 1: Track Overview */}
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard icon={MapPin} label="Track" value={guide.track_name} />
            <StatCard icon={Ruler} label="Length" value={formatLength(guide.length_m)} />
            <StatCard
              icon={Navigation}
              label="Turns"
              value={String(guide.n_corners)}
            />
            <StatCard
              icon={Mountain}
              label="Elevation"
              value={guide.elevation_range_m ? `${guide.elevation_range_m}m` : '—'}
            />
          </div>

          {/* Section 2: Key Corners */}
          {guide.key_corners.length > 0 && (
            <CollapsibleSection
              title="Key Corners"
              defaultOpen={!hasSeen}
              count={guide.key_corners.length}
            >
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {guide.key_corners.map((kc) => (
                  <KeyCornerCard key={kc.number} corner={kc} />
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Section 3: All Corners */}
          <CollapsibleSection
            title="All Corners"
            defaultOpen={false}
            count={guide.corners.length}
          >
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-[var(--cata-border)]">
                    <th className="pb-1.5 pl-2 pr-3 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">Corner</th>
                    <th className="pb-1.5 pr-3 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">Dir</th>
                    <th className="pb-1.5 pr-3 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">Type</th>
                    <th className="pb-1.5 pr-3 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">Elevation</th>
                    <th className="pb-1.5 pr-2 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">Special</th>
                  </tr>
                </thead>
                <tbody>
                  {guide.corners.map((c) => (
                    <CornerRow key={c.number} corner={c} />
                  ))}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>

          {/* Section 4: Landmarks */}
          {guide.landmarks.length > 0 && (
            <CollapsibleSection
              title="Landmarks"
              defaultOpen={false}
              count={guide.landmarks.length}
            >
              <LandmarkList landmarks={guide.landmarks} />
            </CollapsibleSection>
          )}
        </div>
      )}
    </div>
  );
}
