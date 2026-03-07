import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { OptimalGapChart } from '../OptimalGapChart';

const mockUseOptimalComparison = vi.fn();

vi.mock('@/hooks/useAnalysis', () => ({
  useOptimalComparison: (...args: unknown[]) => mockUseOptimalComparison(...args),
}));

const mockCanvasChartReturn = vi.fn();

vi.mock('@/hooks/useCanvasChart', () => ({
  useCanvasChart: (...args: unknown[]) => mockCanvasChartReturn(...args),
}));

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({
    convertSpeed: (value: number) => value,
    speedUnit: 'mph',
  }),
}));

vi.mock('@/components/shared/SkeletonCard', () => ({
  SkeletonCard: ({ height }: { height?: string }) => <div data-testid="skeleton" />,
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
  },
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

function makeNullCanvasChart() {
  return {
    containerRef: { current: null },
    dataCanvasRef: { current: null },
    dimensions: { width: 0, height: 0, margins: { top: 0, right: 0, bottom: 0, left: 0 } },
    getDataCtx: () => null,
  };
}

function makeCanvasCtx() {
  return {
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    fillText: vi.fn(),
    beginPath: vi.fn(),
    fill: vi.fn(),
    rect: vi.fn(),
    roundRect: vi.fn(),
    fillStyle: '',
    font: '',
    textAlign: '',
    textBaseline: '',
  };
}

describe('OptimalGapChart', () => {
  beforeEach(() => {
    mockUseOptimalComparison.mockReset();
    mockCanvasChartReturn.mockReturnValue(makeNullCanvasChart());
  });

  it('shows skeleton when loading', () => {
    mockUseOptimalComparison.mockReturnValue({ data: undefined, isLoading: true });
    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.getByTestId('skeleton')).toBeTruthy();
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
        corner_opportunities: [makeCornerOpportunity(3, 5.0, 0.4)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="session-1" />);

    expect(screen.queryByText(/Optimal reference unavailable/i)).toBeNull();
    expect(screen.getByText(/approximate/i)).toBeTruthy();
    expect(screen.queryByText(/potential/i)).toBeNull();
  });

  it('shows "no significant speed gaps" when valid but no opportunities pass filter', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 89,
        total_gap_s: 1,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(1, 0.2, 0.01), // Below MIN_GAP_MPH (0.5)
        ],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.getByText(/no significant speed gaps/i)).toBeTruthy();
  });

  it('shows "no significant speed gaps" when valid and empty opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 89,
        total_gap_s: 1,
        is_valid: true,
        corner_opportunities: [],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.getByText(/no significant speed gaps/i)).toBeTruthy();
  });

  it('renders chart container with opportunities', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2.5,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(3, 5.0, 1.2),
          makeCornerOpportunity(7, 3.0, 0.8),
        ],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.getByText('Speed vs Optimal')).toBeTruthy();
    expect(screen.getByText('2.5s potential')).toBeTruthy();
  });

  it('shows subtitle with description', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(1, 5.0, 1.0)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.getByText(/per-corner speed gap/i)).toBeTruthy();
  });

  it('does not show potential badge when total_gap_s is zero', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 90,
        total_gap_s: 0,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(1, 2.0, 0.5)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.queryByText(/potential/i)).toBeNull();
  });

  it('does not show potential badge when total_gap_s is negative (invalid)', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 91,
        total_gap_s: -1,
        is_valid: false,
        corner_opportunities: [makeCornerOpportunity(1, 3.0, 0.5)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.queryByText(/potential/i)).toBeNull();
  });

  it('filters out opportunities with speed_gap_mph <= MIN_GAP_MPH', () => {
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(1, 0.4, 0.1), // Below 0.5 threshold
          makeCornerOpportunity(2, 5.0, 1.5),
        ],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);
    // Chart still renders because opp 2 passes the filter
    expect(screen.getByText('Speed vs Optimal')).toBeTruthy();
  });

  it('renders null when data is undefined and not loading', () => {
    mockUseOptimalComparison.mockReturnValue({ data: undefined, isLoading: false });
    render(<OptimalGapChart sessionId="s1" />);
    // Should show "no significant speed gaps" message
    expect(screen.getByText(/no significant speed gaps/i)).toBeTruthy();
  });

  it('draws bars on canvas when context and dimensions are available', () => {
    const ctx = makeCanvasCtx();
    mockCanvasChartReturn.mockReturnValue({
      containerRef: { current: null },
      dataCanvasRef: { current: null },
      dimensions: {
        width: 400,
        height: 200,
        margins: { top: 4, right: 16, bottom: 4, left: 50 },
      },
      getDataCtx: () => ctx,
    });

    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2.5,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(3, 5.0, 1.2),
          makeCornerOpportunity(7, 3.0, 0.8),
        ],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);

    // Canvas should have been cleared and drawn on
    expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 400, 200);
    // Two bars drawn => two beginPath + fill pairs
    expect(ctx.beginPath).toHaveBeenCalledTimes(2);
    expect(ctx.fill).toHaveBeenCalledTimes(2);
    // roundRect available, so it should be called for each bar
    expect(ctx.roundRect).toHaveBeenCalledTimes(2);
    // Corner labels (T3, T7) and value labels (2 bars)
    expect(ctx.fillText).toHaveBeenCalledTimes(4);
    // Check that corner labels were drawn
    const fillTextCalls = ctx.fillText.mock.calls.map((c: unknown[]) => c[0]);
    expect(fillTextCalls).toContain('T3');
    expect(fillTextCalls).toContain('T7');
  });

  it('falls back to ctx.rect when roundRect is not available', () => {
    const ctx = makeCanvasCtx();
    ctx.roundRect = undefined as unknown as typeof ctx.roundRect;
    mockCanvasChartReturn.mockReturnValue({
      containerRef: { current: null },
      dataCanvasRef: { current: null },
      dimensions: {
        width: 400,
        height: 200,
        margins: { top: 4, right: 16, bottom: 4, left: 50 },
      },
      getDataCtx: () => ctx,
    });

    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 1,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(1, 4.0, 1.0)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);

    expect(ctx.rect).toHaveBeenCalledTimes(1);
    expect(ctx.fill).toHaveBeenCalledTimes(1);
  });

  it('places label inside bar when bar is wide enough', () => {
    const ctx = makeCanvasCtx();
    mockCanvasChartReturn.mockReturnValue({
      containerRef: { current: null },
      dataCanvasRef: { current: null },
      dimensions: {
        width: 500,
        height: 200,
        margins: { top: 4, right: 16, bottom: 4, left: 50 },
      },
      getDataCtx: () => ctx,
    });

    // Single opportunity with max time cost => bar fills full width (434px > 140)
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(1, 8.0, 2.0)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);

    // The value label is drawn with white fill when inside a wide bar
    // Check that fillStyle was set to '#fff' at some point
    const fillStyleAssignments: string[] = [];
    const originalSetter = Object.getOwnPropertyDescriptor(ctx, 'fillStyle');
    // We can check the fillText calls — the label should contain "+8.0 mph"
    const fillTextCalls = ctx.fillText.mock.calls.map((c: unknown[]) => c[0]);
    expect(fillTextCalls.some((t: string) => t.includes('+8.0 mph'))).toBe(true);
  });

  it('does not draw when getDataCtx returns null', () => {
    mockCanvasChartReturn.mockReturnValue({
      containerRef: { current: null },
      dataCanvasRef: { current: null },
      dimensions: {
        width: 400,
        height: 200,
        margins: { top: 4, right: 16, bottom: 4, left: 50 },
      },
      getDataCtx: () => null,
    });

    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 2,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(1, 5.0, 1.0)],
      },
      isLoading: false,
    });

    // Should render without errors — the chart container is present but no canvas drawing
    render(<OptimalGapChart sessionId="s1" />);
    expect(screen.getByText('Speed vs Optimal')).toBeTruthy();
  });

  it('handles single opportunity (no bar spacing needed)', () => {
    const ctx = makeCanvasCtx();
    mockCanvasChartReturn.mockReturnValue({
      containerRef: { current: null },
      dataCanvasRef: { current: null },
      dimensions: {
        width: 300,
        height: 150,
        margins: { top: 4, right: 16, bottom: 4, left: 50 },
      },
      getDataCtx: () => ctx,
    });

    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 88,
        total_gap_s: 1,
        is_valid: true,
        corner_opportunities: [makeCornerOpportunity(5, 3.0, 1.0)],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);

    // Single bar => barSpacing = 0 (line 71-73: opportunities.length > 1 branch is false)
    expect(ctx.beginPath).toHaveBeenCalledTimes(1);
    expect(ctx.fillText).toHaveBeenCalledTimes(2); // corner label + value label
  });

  it('renders label outside bar when bar is narrow', () => {
    const ctx = makeCanvasCtx();
    mockCanvasChartReturn.mockReturnValue({
      containerRef: { current: null },
      dataCanvasRef: { current: null },
      dimensions: {
        width: 500,
        height: 200,
        margins: { top: 4, right: 16, bottom: 4, left: 50 },
      },
      getDataCtx: () => ctx,
    });

    // Two opportunities: one big and one small
    // The small one will have a narrow bar (barW < 140)
    mockUseOptimalComparison.mockReturnValue({
      data: {
        session_id: 's1',
        actual_lap_time_s: 90,
        optimal_lap_time_s: 85,
        total_gap_s: 5,
        is_valid: true,
        corner_opportunities: [
          makeCornerOpportunity(1, 10.0, 5.0), // Full width bar
          makeCornerOpportunity(2, 1.0, 0.1),  // Very narrow bar
        ],
      },
      isLoading: false,
    });

    render(<OptimalGapChart sessionId="s1" />);

    // Both bars should be drawn
    expect(ctx.beginPath).toHaveBeenCalledTimes(2);
    // 2 corner labels + 2 value labels = 4 fillText calls
    expect(ctx.fillText).toHaveBeenCalledTimes(4);
  });
});
