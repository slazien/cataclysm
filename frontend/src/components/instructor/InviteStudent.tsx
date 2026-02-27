'use client';

import { useState, useCallback } from 'react';
import { useCreateInvite } from '@/hooks/useInstructor';
import { UserPlus, Copy, Check, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export function InviteStudent() {
  const invite = useCreateInvite();
  const [copied, setCopied] = useState(false);
  const [code, setCode] = useState<string | null>(null);

  const handleGenerate = useCallback(async () => {
    const result = await invite.mutateAsync();
    setCode(result.invite_code);
    setCopied(false);
  }, [invite]);

  const handleCopy = useCallback(async () => {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <div className="flex flex-col gap-3">
      <button
        type="button"
        onClick={handleGenerate}
        disabled={invite.isPending}
        className={cn(
          'flex items-center justify-center gap-2 rounded-lg border border-[var(--cata-border)] px-4 py-2.5 text-sm font-medium transition-colors',
          'bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]',
          invite.isPending && 'opacity-60',
        )}
      >
        {invite.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <UserPlus className="h-4 w-4" />
        )}
        Generate Invite Code
      </button>

      {code && (
        <div className="flex items-center gap-2 rounded-lg border border-[var(--cata-border)] bg-[var(--bg-surface)] px-4 py-3">
          <code className="flex-1 font-mono text-sm text-[var(--text-primary)]">
            {code}
          </code>
          <button
            type="button"
            onClick={handleCopy}
            className="rounded p-1 text-[var(--text-muted)] transition-colors hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            {copied ? (
              <Check className="h-4 w-4 text-[var(--color-throttle)]" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </button>
        </div>
      )}

      {invite.isError && (
        <p className="text-xs text-[var(--color-brake)]">
          Failed to generate invite code. Please try again.
        </p>
      )}
    </div>
  );
}
