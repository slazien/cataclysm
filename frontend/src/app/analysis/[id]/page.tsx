'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSessionStore } from '@/stores';

export default function AnalysisPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const router = useRouter();
  const setActiveSession = useSessionStore((s) => s.setActiveSession);

  useEffect(() => {
    params.then(({ id }) => {
      setActiveSession(id);
      router.replace('/');
    });
  }, [params, router, setActiveSession]);

  return (
    <div className="flex h-screen items-center justify-center">
      <p className="text-sm text-[var(--text-secondary)]">Loading analysis...</p>
    </div>
  );
}
