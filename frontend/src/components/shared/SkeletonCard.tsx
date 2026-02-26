import { cn } from '@/lib/utils';

interface SkeletonCardProps {
  height?: string;
  className?: string;
}

export function SkeletonCard({ height = 'h-24', className }: SkeletonCardProps) {
  return (
    <div className={cn('animate-pulse rounded-lg bg-[var(--bg-elevated)]', height, className)} />
  );
}
