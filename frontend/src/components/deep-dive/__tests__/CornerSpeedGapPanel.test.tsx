import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { CornerSpeedGapPanel } from '../CornerSpeedGapPanel';

const mockUseOptimalComparison = vi.fn();
const mockSelectCorner = vi.fn();

vi.mock('@/hooks/useAnalysis', () => ({
  useOptimalComparison: (...args: unknown[]) => mockUseOptimalComparison(...args),
}));

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({
    convertSpeed: (value: number) => value,
    speedUnit: 'mph',
  }),
}));

vi.mock('@/stores', () => ({
  useAnalysisStore: (selector: (state: { selectCorner: typeof mockSelectCorner }) => unknown) =>
    selector({ selectCorner: mockSelectCorner }),
}));

vi.mock('@/components/shared/SkeletonCard', () => ({
  SkeletonCard: ({ height }: { height?: string }) => <div data-testid="skeleton" />,
}));

vi.mock('@/components/shared/InfoTooltip', () => ({
  InfoTooltip: () => null,
}));

vi.mock('@/lib/utils', () => ({
  cn: (...args: (string | boolean | undefined | null)[]) => args.filter(Boolean).join(' '),
}));

vi.mock('@/lib/cornerUtils', () => ({
  parseCornerNumber: (id: string) => {
    const match = id.match(/\d+/);
    return match ? parseInt(match[0], 10) : null;
  },
}));

vi.mock('motion/react', () => ({
  motion: {
    div: ({
      children,
      className,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
    }) => (
      <div className={className} {...props}>
        {children}
      </div>
    ),
    button: ({
      children,
      className,
      onClick,
      onMouseEnter,
      onMouseLeave,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      onClick?: () => void;
      onMouseEnter?: () => void;
      onMouseLeave?: () => void;
    }) => (
      <button
        className={className}
        onClick={onClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
      >
        {children}
      </button>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

function makeCornerOpportunity(
  corner_number: number,
  speed_gap_mph: number,
  time_cost_s: number,
) {
  return {
    corner_number,
    speed_gap_mph,
    time_cost_s,
    actual_min_speed_mph: 50,
    optimal_min_speed_mph: 50 + speed_gap_mph,
  };
}

describe('CornerSpeedGapPanel', () => {
  beforeEach(() => {
    mockUseOptimalComparison.mockReset();
    mockSelectCorner.mockReset();
  });

  it('shows skeleton when loading', () => {
    mockUseOptimalComparison.mockReturnValue({ data: undefined, isLoading: true });
    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);
    expect(screen.getByTestId('skeleton')).toBeTruthy();
  });

  it('renders nothing when no opportunities and no focused corner (valid comparison)', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [],
      },
      isLoading: false,
    });

    const { container } = render(
      <CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('shows unavailable state when invalid with no opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
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
    });

    render(<CornerSpeedGapPanel sessionId="session-1" selectedCorner={null} />);

    expect(screen.getByText(/physics-optimal reference was invalid/i)).toBeTruthy();
    expect(screen.queryByText(/ahead/i)).toBeNull();
    expect(screen.queryByText(/strength/i)).toBeNull();
  });

  it('shows warning banner with data when invalid but has corner opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 'session-1',
        actual_lap_time_s: 100,
        optimal_lap_time_s: 101,
        total_gap_s: -1,
        is_valid: false,
        invalid_reasons: ['aggregate_optimal_slower_than_actual'],
        corner_opportunities: [makeCornerOpportunity(5, 4.0, 0.3)],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="session-1" selectedCorner={null} />);

    expect(screen.queryByText(/physics-optimal reference was invalid/i)).toBeNull();
    expect(screen.getByText(/approximate/i)).toBeTruthy();
    expect(screen.queryByText(/total/i)).toBeNull();
  });

  it('renders gap bars for valid opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(3, 5.0, 0.8),
          makeCornerOpportunity(7, 3.0, 0.5),
        ],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);

    expect(screen.getByText('Speed Gap vs Optimal')).toBeTruthy();
    expect(screen.getByText(/T3/)).toBeTruthy();
    expect(screen.getByText(/T7/)).toBeTruthy();
  });

  it('shows total gap badge when valid and positive', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2.5,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(1, 5.0, 2.5)],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);
    expect(screen.getByText('2.5s total')).toBeTruthy();
  });

  it('filters out opportunities below MIN_GAP_MPH threshold', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 1,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(1, 0.1, 0.01), // Below 0.3 mph threshold
          makeCornerOpportunity(2, 5.0, 0.8),
        ],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);
    expect(screen.queryByText(/T1/)).toBeNull();
    expect(screen.getByText(/T2/)).toBeTruthy();
  });

  it('filters out opportunities with zero time cost', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 1,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(1, 5.0, 0), // Zero time cost
          makeCornerOpportunity(2, 3.0, 0.5),
        ],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);
    expect(screen.queryByText(/T1/)).toBeNull();
    expect(screen.getByText(/T2/)).toBeTruthy();
  });

  it('shows focused corner breakdown view when a corner is selected', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(5, 4.0, 0.6),
        ],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={5} />);
    expect(screen.getByText('Turn 5 Breakdown')).toBeTruthy();
    expect(screen.getByText('Your Min Speed')).toBeTruthy();
    expect(screen.getByText('Optimal Min Speed')).toBeTruthy();
  });

  it('shows "no measurable gap" for corner with zero time cost in focus view', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 0,
        is_valid: true,
        corner_opportunities: [
          { corner_number: 3, speed_gap_mph: 0.1, time_cost_s: 0, actual_min_speed_mph: 60, optimal_min_speed_mph: 60.1 },
        ],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={3} />);
    expect(screen.getByText('No measurable gap')).toBeTruthy();
  });

  it('clicking a gap bar calls selectCorner', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(5, 4.0, 0.6)],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);
    const barButton = screen.getByText(/T5/).closest('button')!;
    fireEvent.click(barButton);
    expect(mockSelectCorner).toHaveBeenCalledWith('T5');
  });

  it('renders null when comparison data is null/undefined and not loading', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: undefined,
      isLoading: false,
    });

    const { container } = render(
      <CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('handles mouseEnter and mouseLeave on gap bar', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(5, 4.0, 0.6)],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);

    const barButton = screen.getByText(/T5/).closest('button')!;

    // mouseEnter triggers onHover(corner_number)
    fireEvent.mouseEnter(barButton);
    // mouseLeave triggers onHover(null)
    fireEvent.mouseLeave(barButton);

    // The component should still render without errors
    expect(screen.getByText(/T5/)).toBeTruthy();
  });

  it('shows straights row when residual gap exceeds 0.1s', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 87,
        total_gap_s: 3.0,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(3, 5.0, 1.2)],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);

    expect(screen.getByText('Str.')).toBeTruthy();
    expect(screen.getByText(/straights/i)).toBeTruthy();
  });

  it('does not show straights row when residual is negligible', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88.8,
        total_gap_s: 1.2,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(3, 5.0, 1.15)],
      },
      isLoading: false,
    });

    render(<CornerSpeedGapPanel sessionId="s1" selectedCorner={null} />);

    expect(screen.queryByText('Str.')).toBeNull();
  });
});
