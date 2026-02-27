'use client';

import { useState, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Upload, MapPin, Clock, Trophy, AlertCircle, Loader2 } from 'lucide-react';
import { getShareMetadata, uploadToShare } from '@/lib/api';
import { formatLapTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { DeltaTimeChart } from '@/components/comparison/DeltaTimeChart';
import type { ShareComparisonResult } from '@/lib/types';

export default function SharePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;

  const { data: meta, isLoading, error } = useQuery({
    queryKey: ['share-metadata', token],
    queryFn: () => getShareMetadata(token),
    enabled: !!token,
  });

  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<ShareComparisonResult | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = useCallback(
    async (files: FileList | File[]) => {
      setUploading(true);
      setUploadError(null);
      try {
        const fileArray = Array.from(files);
        const result = await uploadToShare(token, fileArray);
        setComparison(result);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : 'Upload failed');
      } finally {
        setUploading(false);
      }
    },
    [token],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length > 0) {
        handleUpload(e.dataTransfer.files);
      }
    },
    [handleUpload],
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-[var(--text-secondary)]" />
          <p className="text-sm text-[var(--text-secondary)]">Loading share details...</p>
        </div>
      </div>
    );
  }

  // Error or not found
  if (error || !meta) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="mx-auto max-w-md rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8 text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[var(--color-brake)]" />
          <h1 className="mb-2 text-lg font-semibold text-[var(--text-primary)]">
            Share Link Not Found
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            This share link is invalid or has been removed.
          </p>
        </div>
      </div>
    );
  }

  // Expired
  if (meta.is_expired) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <div className="mx-auto max-w-md rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-8 text-center">
          <AlertCircle className="mx-auto mb-3 h-8 w-8 text-orange-400" />
          <h1 className="mb-2 text-lg font-semibold text-[var(--text-primary)]">
            Share Link Expired
          </h1>
          <p className="text-sm text-[var(--text-secondary)]">
            This share link has expired. Ask the driver to create a new one.
          </p>
        </div>
      </div>
    );
  }

  // Comparison result view
  if (comparison) {
    const aFaster = comparison.delta_s < 0;
    const deltaAbs = Math.abs(comparison.delta_s);

    return (
      <div className="min-h-screen bg-[var(--bg-primary)]">
        <div className="mx-auto flex max-w-4xl flex-col gap-6 p-4 lg:p-8">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
              Comparison Results
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {meta.track_name}
            </p>
          </div>

          {/* Winner Banner */}
          <div
            className={cn(
              'rounded-lg border px-5 py-4',
              aFaster
                ? 'border-[var(--color-throttle)]/30 bg-[var(--color-throttle)]/5'
                : 'border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5',
            )}
          >
            <div className="flex items-center justify-center gap-3">
              <Trophy
                className={cn(
                  'h-5 w-5',
                  aFaster ? 'text-[var(--color-throttle)]' : 'text-[var(--color-brake)]',
                )}
              />
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {aFaster ? meta.inviter_name : 'You'}{aFaster ? '' : ''} {aFaster ? 'is' : 'are'} faster by{' '}
                <span className="font-mono font-semibold">{deltaAbs.toFixed(3)}s</span>
              </p>
            </div>
          </div>

          {/* Session Cards */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div
              className={cn(
                'rounded-lg border px-5 py-4',
                aFaster
                  ? 'border-[var(--color-throttle)]/30 bg-[var(--bg-surface)]'
                  : 'border-[var(--cata-border)] bg-[var(--bg-surface)]',
              )}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  {meta.inviter_name}
                </span>
                {aFaster && (
                  <span className="rounded-full bg-[var(--color-throttle)]/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--color-throttle)]">
                    Faster
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
                  {comparison.session_a_best_lap !== null
                    ? formatLapTime(comparison.session_a_best_lap)
                    : '--:--'}
                </span>
              </div>
            </div>

            <div
              className={cn(
                'rounded-lg border px-5 py-4',
                !aFaster
                  ? 'border-[var(--color-throttle)]/30 bg-[var(--bg-surface)]'
                  : 'border-[var(--cata-border)] bg-[var(--bg-surface)]',
              )}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  Your Session
                </span>
                {!aFaster && (
                  <span className="rounded-full bg-[var(--color-throttle)]/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-[var(--color-throttle)]">
                    Faster
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-[var(--text-muted)]" />
                <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
                  {comparison.session_b_best_lap !== null
                    ? formatLapTime(comparison.session_b_best_lap)
                    : '--:--'}
                </span>
              </div>
            </div>
          </div>

          {/* Delta-T Chart */}
          {comparison.distance_m.length > 0 && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
              <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
                Delta-T Over Distance
              </h2>
              <div className="h-64">
                <DeltaTimeChart
                  distance_m={comparison.distance_m}
                  delta_time_s={comparison.delta_time_s}
                  totalDelta={comparison.delta_s}
                />
              </div>
            </div>
          )}

          {/* Corner Deltas */}
          {comparison.corner_deltas.length > 0 && (
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
              <h2 className="mb-4 text-sm font-medium text-[var(--text-primary)]">
                Corner-by-Corner Comparison
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--cata-border)]">
                      <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        Corner
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        {meta.inviter_name}
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        You
                      </th>
                      <th className="px-3 py-2 text-right text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        Delta
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.corner_deltas.map((cd) => {
                      const isPositive = cd.speed_diff_mph > 0;
                      const isNegative = cd.speed_diff_mph < 0;
                      return (
                        <tr
                          key={cd.corner_number}
                          className="border-b border-[var(--cata-border)]/50 transition-colors hover:bg-[var(--bg-elevated)]"
                        >
                          <td className="px-3 py-2 font-medium text-[var(--text-primary)]">
                            T{cd.corner_number}
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-[var(--text-secondary)]">
                            {cd.a_min_speed_mph.toFixed(1)} mph
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-[var(--text-secondary)]">
                            {cd.b_min_speed_mph.toFixed(1)} mph
                          </td>
                          <td
                            className={cn(
                              'px-3 py-2 text-right font-mono font-medium',
                              isPositive && 'text-[var(--color-throttle)]',
                              isNegative && 'text-[var(--color-brake)]',
                              !isPositive && !isNegative && 'text-[var(--text-muted)]',
                            )}
                          >
                            {isPositive ? '+' : ''}
                            {cd.speed_diff_mph.toFixed(1)} mph
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Main share landing page - upload zone
  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <div className="mx-auto flex max-w-2xl flex-col items-center gap-8 p-4 pt-16 lg:p-8 lg:pt-24">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
            Compare Your Laps
          </h1>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--text-primary)]">{meta.inviter_name}</span>{' '}
            wants to compare sessions with you
          </p>
        </div>

        {/* Session Info Card */}
        <div className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
          <div className="flex items-center gap-3">
            <MapPin className="h-5 w-5 text-[var(--text-muted)]" />
            <div>
              <p className="font-medium text-[var(--text-primary)]">{meta.track_name}</p>
              {meta.best_lap_time_s !== null && (
                <p className="text-sm text-[var(--text-secondary)]">
                  Their best lap:{' '}
                  <span className="font-mono font-semibold text-[var(--text-primary)]">
                    {formatLapTime(meta.best_lap_time_s)}
                  </span>
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Upload Zone */}
        <div
          className={cn(
            'w-full cursor-pointer rounded-lg border-2 border-dashed p-12 text-center transition-colors',
            dragOver
              ? 'border-[var(--color-throttle)] bg-[var(--color-throttle)]/5'
              : 'border-[var(--cata-border)] hover:border-[var(--text-muted)]/40',
            uploading && 'pointer-events-none opacity-60',
          )}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleUpload(e.target.files);
              }
            }}
          />
          {uploading ? (
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-[var(--text-secondary)]" />
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Processing your session...
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                This may take a few seconds
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Upload className="h-8 w-8 text-[var(--text-muted)]" />
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Drop your RaceChrono CSV here
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                or click to browse
              </p>
            </div>
          )}
        </div>

        {uploadError && (
          <div className="w-full rounded-lg border border-[var(--color-brake)]/30 bg-[var(--color-brake)]/5 px-4 py-3 text-sm text-[var(--color-brake)]">
            {uploadError}
          </div>
        )}
      </div>
    </div>
  );
}
