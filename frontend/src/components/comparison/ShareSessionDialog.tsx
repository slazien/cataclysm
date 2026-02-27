'use client';

import { useState, useCallback } from 'react';
import { Link2, Check, Copy, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { createShareLink } from '@/lib/api';
import { useUiStore } from '@/stores';

interface ShareSessionDialogProps {
  sessionId: string;
}

export function ShareSessionDialog({ sessionId }: ShareSessionDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [trackName, setTrackName] = useState<string>('');
  const [expiresAt, setExpiresAt] = useState<string>('');
  const [copied, setCopied] = useState(false);
  const addToast = useUiStore((s) => s.addToast);

  const handleCreate = useCallback(async () => {
    setLoading(true);
    try {
      const result = await createShareLink(sessionId);
      const fullUrl = `${window.location.origin}${result.share_url}`;
      setShareUrl(fullUrl);
      setTrackName(result.track_name);
      setExpiresAt(result.expires_at);
    } catch {
      addToast({ message: 'Failed to create share link', type: 'info' });
    } finally {
      setLoading(false);
    }
  }, [sessionId, addToast]);

  const handleCopy = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      addToast({ message: 'Share link copied!', type: 'info' });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textArea = document.createElement('textarea');
      textArea.value = shareUrl;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [shareUrl, addToast]);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      // Reset state when dialog closes
      setShareUrl(null);
      setCopied(false);
      setLoading(false);
    }
  };

  const expiresDate = expiresAt
    ? new Date(expiresAt).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      })
    : '';

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 border-[var(--cata-border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <Link2 className="h-3.5 w-3.5" />
          Share for Comparison
        </Button>
      </DialogTrigger>
      <DialogContent className="border-[var(--cata-border)] bg-[var(--bg-surface)]">
        <DialogHeader>
          <DialogTitle className="text-[var(--text-primary)]">
            Share Session for Comparison
          </DialogTitle>
          <DialogDescription className="text-[var(--text-secondary)]">
            Generate a link your friend can use to upload their session and compare lap times.
          </DialogDescription>
        </DialogHeader>

        {!shareUrl ? (
          <div className="flex flex-col items-center gap-4 py-4">
            <p className="text-center text-sm text-[var(--text-secondary)]">
              Your friend will be able to upload their own RaceChrono CSV and see a side-by-side
              comparison of your best laps.
            </p>
            <Button
              onClick={handleCreate}
              disabled={loading}
              className="gap-2"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Link2 className="h-4 w-4" />
              )}
              {loading ? 'Generating...' : 'Generate Share Link'}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-4 py-2">
            <div className="rounded-lg border border-[var(--cata-border)] bg-[var(--bg-elevated)] p-3">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                Track
              </p>
              <p className="text-sm font-medium text-[var(--text-primary)]">{trackName}</p>
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-elevated)] p-3">
              <input
                type="text"
                readOnly
                value={shareUrl}
                className="flex-1 bg-transparent font-mono text-xs text-[var(--text-primary)] outline-none"
              />
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={handleCopy}
                className="shrink-0"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-[var(--color-throttle)]" />
                ) : (
                  <Copy className="h-4 w-4 text-[var(--text-secondary)]" />
                )}
              </Button>
            </div>

            {expiresDate && (
              <p className="text-xs text-[var(--text-muted)]">
                This link expires on {expiresDate}.
              </p>
            )}
          </div>
        )}

        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}
