'use client';

import { useRef, useState, useCallback } from 'react';
import { Upload, FileSpreadsheet } from 'lucide-react';
import { useSessionStore } from '@/stores';
import { useUploadSessions } from '@/hooks/useSession';
import { Button } from '@/components/ui/button';

export function WelcomeScreen() {
  const uploadMutation = useUploadSessions();
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loadingSample, setLoadingSample] = useState(false);

  const handleFiles = useCallback(
    (files: File[]) => {
      if (files.length === 0) return;
      uploadMutation.mutate(files, {
        onSuccess: (data) => {
          if (data.session_ids.length > 0) {
            setActiveSession(data.session_ids[0]);
          }
        },
      });
    },
    [uploadMutation, setActiveSession],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files).filter((f) =>
        f.name.endsWith('.csv'),
      );
      handleFiles(files);
    },
    [handleFiles],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files) handleFiles(Array.from(files));
      e.target.value = '';
    },
    [handleFiles],
  );

  const handleSampleData = useCallback(async () => {
    setLoadingSample(true);
    try {
      const response = await fetch('/sample-session/barber_sample.csv');
      const blob = await response.blob();
      const file = new File([blob], 'barber_sample.csv', { type: 'text/csv' });
      handleFiles([file]);
    } catch {
      // Sample data not available — silently fail
    } finally {
      setLoadingSample(false);
    }
  }, [handleFiles]);

  return (
    <div className="flex h-full flex-col items-center justify-center gap-8 p-8">
      {/* Hero */}
      <div className="text-center">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">
          Welcome to Cataclysm
        </h1>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          AI-powered telemetry analysis for track day drivers
        </p>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`flex w-full max-w-md cursor-pointer flex-col items-center gap-4 rounded-xl border-2 border-dashed p-10 transition-colors ${
          isDragging
            ? 'border-[var(--cata-accent)] bg-[var(--cata-accent)]/5'
            : 'border-[var(--cata-border)] bg-[var(--bg-surface)] hover:border-[var(--text-muted)]'
        }`}
      >
        <div className="rounded-full bg-[var(--bg-elevated)] p-4">
          <Upload
            className={`h-8 w-8 ${isDragging ? 'text-[var(--cata-accent)]' : 'text-[var(--text-muted)]'}`}
          />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {uploadMutation.isPending ? 'Uploading...' : 'Drop CSV files here'}
          </p>
          <p className="mt-1 text-xs text-[var(--text-muted)]">
            or click to browse — RaceChrono v3 CSV format
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".csv"
          className="hidden"
          onChange={handleFileInput}
        />
      </div>

      {/* Sample data button */}
      <Button
        variant="outline"
        size="sm"
        onClick={handleSampleData}
        disabled={loadingSample}
        className="gap-2"
      >
        <FileSpreadsheet className="h-4 w-4" />
        {loadingSample ? 'Loading sample...' : 'Try with sample data'}
      </Button>

      {/* How to export from RaceChrono */}
      <div className="w-full max-w-sm rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
          How to export from RaceChrono
        </h3>
        <ol className="mt-3 space-y-2 text-sm text-[var(--text-secondary)]">
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-muted)]">
              1
            </span>
            Open session in RaceChrono Pro
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-muted)]">
              2
            </span>
            Tap Export → CSV v3 format
          </li>
          <li className="flex items-start gap-2">
            <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--bg-elevated)] text-xs font-bold text-[var(--text-muted)]">
              3
            </span>
            Include GPS, speed, and lap data channels
          </li>
        </ol>
      </div>
    </div>
  );
}
