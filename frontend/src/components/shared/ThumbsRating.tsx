'use client';

import { ThumbsUp, ThumbsDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ThumbsRatingProps {
  rating: number; // -1, 0, or 1
  onRate: (rating: number) => void;
  disabled?: boolean;
}

export function ThumbsRating({ rating, onRate, disabled }: ThumbsRatingProps) {
  return (
    <div className="inline-flex items-center gap-1">
      <button
        type="button"
        disabled={disabled}
        onClick={() => onRate(rating === 1 ? 0 : 1)}
        title={rating === 1 ? 'Remove rating' : 'Helpful'}
        className={cn(
          'rounded p-1 transition-colors',
          rating === 1
            ? 'text-emerald-400 bg-emerald-400/10'
            : 'text-[var(--text-muted)] hover:text-emerald-400 hover:bg-emerald-400/5',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onRate(rating === -1 ? 0 : -1)}
        title={rating === -1 ? 'Remove rating' : 'Not helpful'}
        className={cn(
          'rounded p-1 transition-colors',
          rating === -1
            ? 'text-red-400 bg-red-400/10'
            : 'text-[var(--text-muted)] hover:text-red-400 hover:bg-red-400/5',
          disabled && 'opacity-50 cursor-not-allowed',
        )}
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
