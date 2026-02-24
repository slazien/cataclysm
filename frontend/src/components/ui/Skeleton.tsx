"use client";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--bg-card)] ${className}`} />;
}

export function ChartSkeleton({ height = 300 }: { height?: number }) {
  return (
    <div className="rounded-lg p-4" style={{ background: "var(--bg-card)", height }}>
      <Skeleton className="mb-4 h-4 w-1/3" />
      <Skeleton className="h-full w-full" />
    </div>
  );
}

export function MetricCardSkeleton() {
  return (
    <div className="rounded-lg p-4" style={{ background: "var(--bg-card)" }}>
      <Skeleton className="mb-2 h-3 w-20" />
      <Skeleton className="mb-1 h-8 w-24" />
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="rounded-lg p-4" style={{ background: "var(--bg-card)" }}>
      <Skeleton className="mb-2 h-8 w-full" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="mb-1 h-6 w-full" />
      ))}
    </div>
  );
}
