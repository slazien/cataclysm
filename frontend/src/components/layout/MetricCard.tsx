"use client";

interface MetricCardProps {
  label: string;
  value: string;
  subtitle?: string;
}

export default function MetricCard({ label, value, subtitle }: MetricCardProps) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
      <p className="text-xs font-medium text-[var(--text-secondary)]">
        {label}
      </p>
      <p className="mt-1 text-2xl font-bold text-[var(--text-primary)]">
        {value}
      </p>
      {subtitle && (
        <p className="mt-0.5 text-xs text-[var(--text-muted)]">{subtitle}</p>
      )}
    </div>
  );
}
