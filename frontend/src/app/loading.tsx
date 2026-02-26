import { CircularProgress } from '@/components/shared/CircularProgress';

export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <CircularProgress size={32} color="var(--accent-blue)" />
    </div>
  );
}
