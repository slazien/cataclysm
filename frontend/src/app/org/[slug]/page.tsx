'use client';

import { useParams } from 'next/navigation';
import { OrgDashboard } from '@/components/org/OrgDashboard';

export default function OrgPage() {
  const params = useParams<{ slug: string }>();

  if (!params.slug) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)]">
        <p className="text-sm text-[var(--text-muted)]">No organization specified.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <OrgDashboard slug={params.slug} />
    </div>
  );
}
