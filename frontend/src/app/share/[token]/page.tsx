'use client';

import { useState, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Upload, MapPin, AlertCircle, Loader2, Calendar, Timer } from 'lucide-react';
import { getShareMetadata, uploadToShare } from '@/lib/api';
import { formatLapTime } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { ComparisonSummary } from '@/components/comparison/ComparisonSummary';
import { SignUpCTA } from '@/components/shared/SignUpCTA';
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
    return (
      <div className="min-h-screen bg-[var(--bg-primary)] pb-24">
        <div className="mx-auto flex w-full min-w-0 max-w-4xl flex-col gap-6 p-4 lg:p-8">
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
              Comparison Results
            </h1>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              {meta.track_name}
            </p>
          </div>
          <ComparisonSummary
            comparison={comparison}
            inviterName={meta.inviter_name ?? 'Driver A'}
            challengerName="You"
            trackName={meta.track_name}
            token={token}
          />
        </div>
        <SignUpCTA
          headline="Get your own AI race engineer"
          subline="Corner-by-corner coaching, progress tracking, and lap comparisons — free"
        />
      </div>
    );
  }

  // Main share landing page - upload zone
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] pb-24">
      <div className="mx-auto flex w-full min-w-0 max-w-2xl flex-col items-center gap-8 p-4 pt-16 lg:p-8 lg:pt-24">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
            Think you&apos;re faster?
          </h1>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            <span className="font-medium text-[var(--text-primary)]">{meta.inviter_name}</span>{' '}
            challenged you to a lap comparison
          </p>
        </div>

        {/* Session Info Card */}
        <div className="w-full rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-5">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <MapPin className="h-5 w-5 shrink-0 text-[var(--text-secondary)]" />
              <p className="font-medium text-[var(--text-primary)]">{meta.track_name}</p>
            </div>
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 pl-8">
              {meta.best_lap_time_s !== null && (
                <div className="flex items-center gap-2">
                  <Timer className="h-4 w-4 text-[var(--text-secondary)]" />
                  <span className="text-sm text-[var(--text-secondary)]">Best lap</span>
                  <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">
                    {formatLapTime(meta.best_lap_time_s)}
                  </span>
                </div>
              )}
              {meta.created_at && (
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-[var(--text-secondary)]" />
                  <span className="text-sm text-[var(--text-secondary)]">
                    {new Date(meta.created_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                  </span>
                </div>
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
              <p className="text-xs text-[var(--text-secondary)]">
                This may take a few seconds
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Upload className="h-8 w-8 text-[var(--color-throttle)]" />
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Upload your session to compare
              </p>
              <p className="text-xs text-[var(--text-secondary)]">
                Drop a RaceChrono CSV or click to browse
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
      <SignUpCTA
        headline="Get your own AI race engineer"
        subline="Corner-by-corner coaching, progress tracking, and lap comparisons — free"
      />
    </div>
  );
}
