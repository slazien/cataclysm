import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { PriorityCardsSection } from '../PriorityCardsSection';

const mockSetActiveView = vi.fn();
const mockSetMode = vi.fn();
const mockSelectCorner = vi.fn();

vi.mock('@/stores', () => ({
  useUiStore: (selector: (state: { setActiveView: typeof mockSetActiveView }) => unknown) =>
    selector({ setActiveView: mockSetActiveView }),
  useAnalysisStore: (
    selector: (state: {
      setMode: typeof mockSetMode;
      selectCorner: typeof mockSelectCorner;
    }) => unknown,
  ) => selector({ setMode: mockSetMode, selectCorner: mockSelectCorner }),
  useSessionStore: (selector: (state: { activeSessionId: string | null }) => unknown) =>
    selector({ activeSessionId: 'test-session' }),
}));

vi.mock('@/hooks/useCoachingFeedback', () => ({
  useCoachingFeedback: () => ({
    getRating: () => 0,
    submitFeedback: vi.fn(),
  }),
}));

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({ resolveSpeed: (text: string) => text }),
}));

vi.mock('@/components/shared/MarkdownText', () => ({
  MarkdownText: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock('@/lib/gradeUtils', () => ({
  worstGrade: (grades: string[]) => grades.sort().pop() ?? 'C',
}));

vi.mock('@/lib/textUtils', () => ({
  extractActionTitle: (text: string) => text,
  formatCoachingText: (text: string) => text,
}));

vi.mock('lucide-react', () => ({
  ArrowRight: ({ className }: { className?: string }) => (
    <svg data-testid="arrow-right" className={className} />
  ),
  ChevronDown: ({ className }: { className?: string }) => (
    <svg data-testid="chevron-down" className={className} />
  ),
  ChevronUp: ({ className }: { className?: string }) => (
    <svg data-testid="chevron-up" className={className} />
  ),
  TrendingUp: ({ className }: { className?: string }) => (
    <svg data-testid="trending-up" className={className} />
  ),
  TrendingDown: ({ className }: { className?: string }) => (
    <svg data-testid="trending-down" className={className} />
  ),
  ThumbsUp: ({ className }: { className?: string }) => (
    <svg data-testid="thumbs-up" className={className} />
  ),
  ThumbsDown: ({ className }: { className?: string }) => (
    <svg data-testid="thumbs-down" className={className} />
  ),
}));

describe('PriorityCardsSection', () => {
  it('renders the "Priority Improvements" heading', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 4, time_cost_s: 0.45, issue: 'Late apex', tip: 'Wait longer' }]}
        isNovice={false}
      />,
    );
    expect(screen.getByText('Priority Improvements')).toBeInTheDocument();
  });

  it('shows bounded opportunity wording instead of a negative loss badge', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 4, time_cost_s: 0.45, issue: 'Late apex', tip: 'Wait longer' }]}
        isNovice={false}
      />,
    );

    expect(screen.getByText('Up to 0.5s')).toBeTruthy();
    expect(screen.queryByText('-0.45s')).toBeNull();
  });

  it('avoids showing a fake gain badge when no positive estimate is available', () => {
    render(
      <PriorityCardsSection
        priorities={[
          { corner: 7, time_cost_s: 0, issue: 'Turn-in timing', tip: 'Reset hands' },
        ]}
        isNovice={false}
      />,
    );

    expect(screen.getByText('Estimate unavailable')).toBeTruthy();
  });

  it('renders turn number for each priority', () => {
    render(
      <PriorityCardsSection
        priorities={[
          { corner: 3, time_cost_s: 0.5, issue: 'Late braking at corner', tip: 'Brake earlier' },
          { corner: 7, time_cost_s: 0.3, issue: 'Missing apex', tip: 'Aim tighter' },
        ]}
        isNovice={false}
      />,
    );
    expect(screen.getByText('Turn 3')).toBeInTheDocument();
    expect(screen.getByText('Turn 7')).toBeInTheDocument();
  });

  it('renders "Explore in Deep Dive" button for each card', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.8, issue: 'Slow exit', tip: 'Open throttle' }]}
        isNovice={false}
      />,
    );
    expect(screen.getByText(/Explore in Deep Dive/)).toBeInTheDocument();
  });

  it('clicking "Explore" calls selectCorner, setMode, setActiveView', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.8, issue: 'Slow exit', tip: 'Open throttle' }]}
        isNovice={false}
      />,
    );
    const exploreButton = screen.getByText(/Explore in Deep Dive/).closest('button')!;
    fireEvent.click(exploreButton);

    expect(mockSelectCorner).toHaveBeenCalledWith('T5');
    expect(mockSetMode).toHaveBeenCalledWith('corner');
    expect(mockSetActiveView).toHaveBeenCalledWith('deep-dive');
  });

  it('shows novice tip when isNovice=true and tip exists', () => {
    render(
      <PriorityCardsSection
        priorities={[
          { corner: 1, time_cost_s: 0.3, issue: 'Entry speed', tip: 'This is a helpful tip' },
        ]}
        isNovice={true}
      />,
    );
    expect(screen.getByText('This is a helpful tip')).toBeInTheDocument();
  });

  it('does not show novice tip when isNovice=false', () => {
    render(
      <PriorityCardsSection
        priorities={[
          { corner: 1, time_cost_s: 0.3, issue: 'Entry speed', tip: 'Hidden tip text' },
        ]}
        isNovice={false}
      />,
    );
    expect(screen.queryByText('Hidden tip text')).not.toBeInTheDocument();
  });

  it('toggle details: clicking "Show details" expands, "Hide details" collapses', () => {
    render(
      <PriorityCardsSection
        priorities={[
          { corner: 2, time_cost_s: 0.4, issue: 'Late trail brake release', tip: 'Hold longer' },
        ]}
        isNovice={false}
      />,
    );

    // Initially collapsed
    expect(screen.getByText('Show details')).toBeInTheDocument();
    expect(screen.queryByText('Hide details')).not.toBeInTheDocument();

    // Expand
    fireEvent.click(screen.getByText('Show details'));
    expect(screen.getByText('Hide details')).toBeInTheDocument();
    expect(screen.queryByText('Show details')).not.toBeInTheDocument();

    // Collapse
    fireEvent.click(screen.getByText('Hide details'));
    expect(screen.getByText('Show details')).toBeInTheDocument();
  });

  it('limits display to 3 priorities maximum', () => {
    render(
      <PriorityCardsSection
        priorities={[
          { corner: 1, time_cost_s: 0.5, issue: 'Issue 1', tip: '' },
          { corner: 2, time_cost_s: 0.4, issue: 'Issue 2', tip: '' },
          { corner: 3, time_cost_s: 0.3, issue: 'Issue 3', tip: '' },
          { corner: 4, time_cost_s: 0.2, issue: 'Issue 4', tip: '' },
        ]}
        isNovice={false}
      />,
    );
    expect(screen.getByText('Turn 1')).toBeInTheDocument();
    expect(screen.getByText('Turn 2')).toBeInTheDocument();
    expect(screen.getByText('Turn 3')).toBeInTheDocument();
    expect(screen.queryByText('Turn 4')).not.toBeInTheDocument();
  });

  it('uses live time cost from optimalComparison when valid', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.4, issue: 'Slow exit', tip: '' }]}
        isNovice={false}
        optimalComparison={{
          session_id: 's1',
          actual_lap_time_s: 90,
          optimal_lap_time_s: 88,
          total_gap_s: 2,
          is_valid: true,
          corner_opportunities: [
            {
              corner_number: 5,
              speed_gap_mph: 3.0,
              time_cost_s: 0.7,
              actual_min_speed_mph: 50,
              optimal_min_speed_mph: 53,
            },
          ],
        }}
      />,
    );
    // Live time cost is 0.7 -> "Up to 0.7s"
    expect(screen.getByText('Up to 0.7s')).toBeInTheDocument();
  });

  it('uses corner_opportunities even when is_valid is false', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.4, issue: 'Slow exit', tip: '' }]}
        isNovice={false}
        optimalComparison={{
          session_id: 's1',
          actual_lap_time_s: 90,
          optimal_lap_time_s: 91,
          total_gap_s: -1,
          is_valid: false,
          corner_opportunities: [
            {
              corner_number: 5,
              speed_gap_mph: 2.0,
              time_cost_s: 0.6,
              actual_min_speed_mph: 48,
              optimal_min_speed_mph: 50,
            },
          ],
        }}
      />,
    );
    // Uses live time_cost_s=0.6 from corner_opportunities, NOT p.time_cost_s=0.4
    expect(screen.getByText('Up to 0.6s')).toBeInTheDocument();
  });

  it('falls back to priority time_cost_s when corner_opportunities is empty', () => {
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.4, issue: 'Slow exit', tip: '' }]}
        isNovice={false}
        optimalComparison={{
          session_id: 's1',
          actual_lap_time_s: 90,
          optimal_lap_time_s: 91,
          total_gap_s: -1,
          is_valid: false,
          corner_opportunities: [],
        }}
      />,
    );
    // No matching corner in opportunities -> falls back to p.time_cost_s = 0.4
    expect(screen.getByText('Up to 0.4s')).toBeInTheDocument();
  });

  it('applies grade-based border color when cornerGrades provided', () => {
    const { container } = render(
      <PriorityCardsSection
        priorities={[
          { corner: 3, time_cost_s: 0.5, issue: 'Braking too late', tip: '' },
        ]}
        isNovice={false}
        cornerGrades={[
          { corner: 3, braking: 'D', trail_braking: 'C', min_speed: 'B', throttle: 'C' },
        ]}
      />,
    );
    // The worst grade for corner 3 is D -> border-l-[var(--grade-d)]
    const card = container.querySelector('.border-l-\\[var\\(--grade-d\\)\\]');
    expect(card).toBeInTheDocument();
  });

  it('shows delta badge when cornerDeltas provided with improvement', () => {
    const deltas = new Map([
      [5, { corner_number: 5, delta_s: 0.3 }],
    ]);
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.4, issue: 'Slow exit', tip: '' }]}
        isNovice={false}
        cornerDeltas={deltas}
      />,
    );
    expect(screen.getByText('0.3s')).toBeInTheDocument();
    expect(screen.getByTestId('trending-up')).toBeInTheDocument();
  });

  it('shows regression delta badge when delta is negative', () => {
    const deltas = new Map([
      [5, { corner_number: 5, delta_s: -0.2 }],
    ]);
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.6, issue: 'Slow exit', tip: '' }]}
        isNovice={false}
        cornerDeltas={deltas}
      />,
    );
    expect(screen.getByText('0.2s')).toBeInTheDocument();
    expect(screen.getByTestId('trending-down')).toBeInTheDocument();
  });

  it('hides delta badge when delta is below threshold', () => {
    const deltas = new Map([
      [5, { corner_number: 5, delta_s: 0.02 }],
    ]);
    render(
      <PriorityCardsSection
        priorities={[{ corner: 5, time_cost_s: 0.4, issue: 'Slow exit', tip: '' }]}
        isNovice={false}
        cornerDeltas={deltas}
      />,
    );
    expect(screen.queryByTestId('trending-up')).not.toBeInTheDocument();
    expect(screen.queryByTestId('trending-down')).not.toBeInTheDocument();
  });

  it('falls back to accent border when no cornerGrades provided', () => {
    const { container } = render(
      <PriorityCardsSection
        priorities={[{ corner: 3, time_cost_s: 0.5, issue: 'Test', tip: '' }]}
        isNovice={false}
      />,
    );
    const card = container.querySelector('.border-l-\\[var\\(--cata-accent\\)\\]');
    expect(card).toBeInTheDocument();
  });
});
