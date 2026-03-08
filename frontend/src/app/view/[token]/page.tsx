'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Loader2, Trophy, Gauge, Target, Timer } from 'lucide-react';
import { getPublicSessionView } from '@/lib/api';
import { formatLapTime } from '@/lib/formatters';
import { RadarChart } from '@/components/shared/RadarChart';
import { TrackOutlineSVG } from '@/components/shared/TrackOutlineSVG';
import { SignUpCTA } from '@/components/shared/SignUpCTA';

export function getPublicScoreDisplay(score: number) {
  return {
    valueText: String(Math.round(Math.min(Math.max(score, 0), 100))),
    labelText: 'Score / 100',
  };
}

export default function PublicViewPage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const { data, isLoading, error } = useQuery({
    queryKey: ['public-view', token],
    queryFn: () => getPublicSessionView(token),
    enabled: !!token,
  });

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--text-secondary)]" />
          <p className="text-sm text-[var(--text-secondary)]">Loading session...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="mx-auto max-w-md rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8 text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[var(--color-brake)]" />
          <h1 className="mb-2 text-lg font-semibold text-[var(--text-primary)]">Session Not Found</h1>
          <p className="text-sm text-[var(--text-secondary)]">
            This session link is invalid or has been removed.
          </p>
        </div>
        <SignUpCTA />
      </div>
    );
  }

  if (data.is_expired) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="mx-auto max-w-md rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8 text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-orange-400" />
          <h1 className="mb-2 text-lg font-semibold text-[var(--text-primary)]">Session Link Expired</h1>
          <p className="text-sm text-[var(--text-secondary)]">This session link has expired.</p>
        </div>
        <SignUpCTA />
      </div>
    );
  }

  const hasSkills =
    data.skill_braking != null &&
    data.skill_trail_braking != null &&
    data.skill_throttle != null &&
    data.skill_line != null;
  const publicScore =
    data.session_score != null ? getPublicScoreDisplay(data.session_score) : null;

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] pb-24">
      <div className="mx-auto flex w-full min-w-0 max-w-2xl flex-col items-center gap-6 p-4 pt-8 lg:p-8 lg:pt-12">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">{data.track_name}</h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            {data.driver_name} &middot; {data.session_date}
          </p>
        </div>

        {/* Track outline */}
        {data.track_coords && data.track_coords.lat.length > 10 && (
          <TrackOutlineSVG coords={data.track_coords} className="opacity-60" />
        )}

        {/* Stats grid */}
        <div className="grid w-full grid-cols-2 gap-3">
          {data.best_lap_time_s != null && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4 text-center">
              <Timer className="mx-auto mb-1 h-5 w-5 text-[var(--text-secondary)]" />
              <p className="font-mono text-lg font-bold text-[var(--text-primary)]">
                {formatLapTime(data.best_lap_time_s)}
              </p>
              <p className="text-xs text-[var(--text-secondary)]">Best Lap</p>
            </div>
          )}
          {data.consistency_score != null && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4 text-center">
              <Target className="mx-auto mb-1 h-5 w-5 text-[var(--text-secondary)]" />
              <p className="font-mono text-lg font-bold text-[var(--text-primary)]">
                {Math.round(data.consistency_score)}%
              </p>
              <p className="text-xs text-[var(--text-secondary)]">Consistency</p>
            </div>
          )}
          {publicScore && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4 text-center">
              <Trophy className="mx-auto mb-1 h-5 w-5 text-[var(--text-secondary)]" />
              <p className="font-mono text-lg font-bold text-[var(--text-primary)]">
                {publicScore.valueText}
              </p>
              <p className="text-xs text-[var(--text-secondary)]">{publicScore.labelText}</p>
            </div>
          )}
          {data.top_speed_mph != null && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4 text-center">
              <Gauge className="mx-auto mb-1 h-5 w-5 text-[var(--text-secondary)]" />
              <p className="font-mono text-lg font-bold text-[var(--text-primary)]">
                {Math.round(data.top_speed_mph)} mph
              </p>
              <p className="text-xs text-[var(--text-secondary)]">Top Speed</p>
            </div>
          )}
        </div>

        {/* Skill radar */}
        {hasSkills && (
          <div className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <h2 className="mb-2 text-center text-sm font-medium text-[var(--text-secondary)]">
              Skill Profile
            </h2>
            <RadarChart
              axes={['Braking', 'Trail Braking', 'Throttle', 'Line']}
              datasets={[
                {
                  label: 'Skills',
                  values: [
                    data.skill_braking!,
                    data.skill_trail_braking!,
                    data.skill_throttle!,
                    data.skill_line!,
                  ],
                  color: '#6366f1',
                },
              ]}
              size={240}
            />
          </div>
        )}

        {/* Coaching summary */}
        {data.coaching_summary && (
          <div className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
            <h2 className="mb-2 text-sm font-medium text-[var(--text-secondary)]">
              AI Coaching Summary
            </h2>
            <blockquote className="border-l-2 border-[#6366f1] pl-3 text-sm italic text-[var(--text-primary)]">
              {data.coaching_summary}
            </blockquote>
          </div>
        )}
      </div>

      <SignUpCTA />
    </div>
  );
}
