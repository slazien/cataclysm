'use client';

import { useState, useCallback } from 'react';
import { Link2, Check, Copy, Loader2, BarChart3, ArrowLeft } from 'lucide-react';
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
import { ComparisonView } from './ComparisonView';

interface ShareSessionDialogProps {
  sessionId: string;
}

export function ShareSessionDialog({ sessionId }: ShareSessionDialogProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [trackName, setTrackName] = useState<string>('');
  const [expiresAt, setExpiresAt] = useState<string>('');
  const [copied, setCopied] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const addToast = useUiStore((s) => s.addToast);

  const handleCreate = useCallback(async () => {
    setLoading(true);
    try {
      const result = await createShareLink(sessionId);
      const fullUrl = `${window.location.origin}${result.share_url}`;
      setShareUrl(fullUrl);
      setShareToken(result.token);
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

  const handleNativeShare = useCallback(async () => {
    if (!shareUrl) return;
    try {
      await navigator.share({
        title: `Compare laps at ${trackName}`,
        text: `I just ran ${trackName} — upload your session and let's see who's faster!`,
        url: shareUrl,
      });
    } catch {
      // User cancelled or not supported — fall back to copy
      handleCopy();
    }
  }, [shareUrl, trackName, handleCopy]);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      // Reset state when dialog closes
      setShareUrl(null);
      setShareToken(null);
      setCopied(false);
      setLoading(false);
      setShowComparison(false);
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
          className="min-h-[44px] gap-1.5 border-[var(--cata-border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <Link2 className="h-3.5 w-3.5" />
          Challenge a Friend
        </Button>
      </DialogTrigger>
      <DialogContent
        className={`border-[var(--cata-border)] bg-[var(--bg-surface)] ${showComparison ? 'max-w-3xl' : ''}`}
      >
        <DialogHeader>
          <DialogTitle className="text-[var(--text-primary)]">
            {showComparison ? (
              <span className="flex items-center gap-2">
                <button
                  onClick={() => setShowComparison(false)}
                  className="text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                Comparison Results
              </span>
            ) : (
              'Challenge a Friend'
            )}
          </DialogTitle>
          {!showComparison && (
            <DialogDescription className="text-[var(--text-secondary)]">
              Send a link — your friend uploads their session and you both get a side-by-side
              comparison with AI coaching.
            </DialogDescription>
          )}
        </DialogHeader>

        {showComparison && shareToken ? (
          <div className="max-h-[70vh] overflow-y-auto py-2">
            <ComparisonView token={shareToken} />
          </div>
        ) : !shareUrl ? (
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
              <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
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

            <div className="flex flex-wrap gap-2">
              {typeof navigator !== 'undefined' && 'share' in navigator && (
                <Button
                  onClick={handleNativeShare}
                  size="sm"
                  className="gap-1.5"
                >
                  <Link2 className="h-3.5 w-3.5" />
                  Share Challenge
                </Button>
              )}

              {shareToken && (
                <Button
                  onClick={() => setShowComparison(true)}
                  variant="outline"
                  size="sm"
                  className="gap-1.5 border-[var(--cata-border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                >
                  <BarChart3 className="h-3.5 w-3.5" />
                  View Comparison
                </Button>
              )}
            </div>

            {expiresDate && (
              <p className="text-xs text-[var(--text-secondary)]">
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
