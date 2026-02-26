'use client';

import { AlertTriangle } from 'lucide-react';

interface ConditionsMismatchAlertProps {
  conditionA?: string | null;
  tempA?: number | null;
  conditionB?: string | null;
  tempB?: number | null;
}

export function ConditionsMismatchAlert({
  conditionA,
  tempA,
  conditionB,
  tempB,
}: ConditionsMismatchAlertProps) {
  const conditionsDiffer =
    conditionA != null && conditionB != null && conditionA !== conditionB;
  const tempDelta =
    tempA != null && tempB != null ? Math.abs(tempA - tempB) : null;
  const tempDiffers = tempDelta !== null && tempDelta >= 5;

  if (!conditionsDiffer && !tempDiffers) return null;

  const details: string[] = [];
  if (conditionsDiffer) {
    details.push(`Track condition: ${conditionA} vs ${conditionB}`);
  }
  if (tempDiffers && tempA != null && tempB != null) {
    details.push(
      `Temperature delta: ${tempDelta!.toFixed(1)}\u00B0C (${tempA.toFixed(1)}\u00B0C vs ${tempB.toFixed(1)}\u00B0C)`,
    );
  }

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
      <div className="min-w-0">
        <p className="text-sm font-medium text-amber-400">Different Conditions</p>
        <p className="mt-0.5 text-xs text-amber-400/80">
          {details.join(' \u2022 ')}
        </p>
      </div>
    </div>
  );
}
