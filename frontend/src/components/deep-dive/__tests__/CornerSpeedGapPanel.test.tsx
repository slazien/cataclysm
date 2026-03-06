import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { CornerSpeedGapPanel } from '../CornerSpeedGapPanel';

vi.mock('@/hooks/useAnalysis', () => ({
  useOptimalComparison: vi.fn(() => ({
    data: {
      session_id: 'session-1',
      actual_lap_time_s: 100,
      optimal_lap_time_s: 101,
      total_gap_s: -1,
      is_valid: false,
      invalid_reasons: ['aggregate_optimal_slower_than_actual'],
      corner_opportunities: [],
    },
    isLoading: false,
  })),
}));

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({
    convertSpeed: (value: number) => value,
    speedUnit: 'mph',
  }),
}));

vi.mock('@/stores', () => ({
  useAnalysisStore: () => vi.fn(),
}));

vi.mock('@/components/shared/SkeletonCard', () => ({
  SkeletonCard: () => <div data-testid="skeleton" />,
}));

vi.mock('@/components/shared/InfoTooltip', () => ({
  InfoTooltip: () => null,
}));

vi.mock('@/lib/utils', () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(' '),
}));

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children, ...props }: { children?: React.ReactNode }) => <div {...props}>{children}</div>,
    button: ({ children, ...props }: { children?: React.ReactNode }) => (
      <button {...props}>{children}</button>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('CornerSpeedGapPanel', () => {
  it('shows a warning state when optimal comparison is invalid', () => {
    render(<CornerSpeedGapPanel sessionId="session-1" selectedCorner={null} />);

    expect(screen.getByText(/physics-optimal reference was invalid/i)).toBeTruthy();
    expect(screen.queryByText(/ahead/i)).toBeNull();
    expect(screen.queryByText(/strength/i)).toBeNull();
  });
});
