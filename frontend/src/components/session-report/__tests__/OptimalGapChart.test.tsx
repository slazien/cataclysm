import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { OptimalGapChart } from '../OptimalGapChart';

const mockUseOptimalComparison = vi.fn();

vi.mock('@/hooks/useAnalysis', () => ({
  useOptimalComparison: (...args: unknown[]) => mockUseOptimalComparison(...args),
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
  beforeEach(() => {
    mockUseOptimalComparison.mockReset();
  });

  it('shows an invalid-reference warning when is_valid=false and no opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
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
    });

    render(<OptimalGapChart sessionId="session-1" />);

    expect(screen.getByText(/Optimal reference unavailable/i)).toBeTruthy();
    expect(screen.getByText(/physics-optimal reference was invalid/i)).toBeTruthy();
    expect(screen.queryByText(/potential/i)).toBeNull();
  });

  it('shows warning banner with chart when is_valid=false but has corner opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 'session-1',
        actual_lap_time_s: 100,
        optimal_lap_time_s: 101,
        total_gap_s: -1,
        is_valid: false,
        invalid_reasons: ['aggregate_optimal_slower_than_actual'],
        corner_opportunities: [
          {
            corner_number: 3,
            speed_gap_mph: 5.0,
            time_cost_s: 0.4,
            actual_min_speed_mph: 55,
            optimal_min_speed_mph: 60,
          },
        ],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="session-1" />);

    expect(screen.queryByText(/Optimal reference unavailable/i)).toBeNull();
    expect(screen.getByText(/approximate/i)).toBeTruthy();
    expect(screen.queryByText(/potential/i)).toBeNull();
  });
});
