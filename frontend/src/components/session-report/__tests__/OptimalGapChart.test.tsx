import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { OptimalGapChart } from '../OptimalGapChart';

vi.mock('@/hooks/useAnalysis', () => ({
  useOptimalComparison: vi.fn(() => ({
    data: {
      session_id: 'session-1',
      actual_lap_time_s: 100,
      optimal_lap_time_s: 101,
      total_gap_s: -1,
      is_valid: false,
      invalid_reasons: ['Optimal reference slower than actual lap'],
      corner_opportunities: [],
    },
    isLoading: false,
  })),
}));

vi.mock('@/hooks/useCanvasChart', () => ({
  useCanvasChart: () => ({
    containerRef: { current: null },
    dataCanvasRef: { current: null },
    dimensions: { width: 0, height: 0, margins: { top: 0, right: 0, bottom: 0, left: 0 } },
    getDataCtx: () => null,
  }),
}));

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({
    convertSpeed: (value: number) => value,
    speedUnit: 'mph',
  }),
}));

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  },
}));

describe('OptimalGapChart', () => {
  it('shows an invalid-reference warning instead of clamping the total gap', () => {
    render(<OptimalGapChart sessionId="session-1" />);

    expect(screen.getByText(/Optimal reference unavailable/i)).toBeTruthy();
    expect(screen.getByText(/physics-optimal reference was invalid/i)).toBeTruthy();
    expect(screen.queryByText(/potential/i)).toBeNull();
  });
});
