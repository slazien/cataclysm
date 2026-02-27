'use client';

import { Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useShareCard } from '@/hooks/useShareCard';
import { useUiStore } from '@/stores';
import { CircularProgress } from '@/components/shared/CircularProgress';

interface ShareButtonProps {
  sessionId: string;
}

export function ShareButton({ sessionId }: ShareButtonProps) {
  const { share, isRendering } = useShareCard(sessionId);
  const addToast = useUiStore((s) => s.addToast);

  async function handleShare() {
    try {
      await share();
      addToast({ message: 'Session card shared!', type: 'info' });
    } catch {
      addToast({ message: 'Failed to generate card', type: 'info' });
    }
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={handleShare}
      disabled={isRendering}
      className="gap-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
    >
      {isRendering ? (
        <CircularProgress size={14} strokeWidth={2} />
      ) : (
        <Share2 className="h-3.5 w-3.5" />
      )}
      Share
    </Button>
  );
}
