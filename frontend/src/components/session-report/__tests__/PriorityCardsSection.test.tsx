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

// Helper: create a MergedPriority fixture with defaults
function mp(overrides: Partial<import('@/lib/types').MergedPriority> & { corner: number }): import('@/lib/types').MergedPriority {
  return {
    time_cost_s: 0,
    issue: '',
    tip: '',
    source: 'llm',
    speed_gap_mph: null,
    brake_gap_m: null,
    exit_straight_time_cost_s: null,
    ...overrides,
  };
}

describe('PriorityCardsSection', () => {
  it('renders the "Priority Improvements" heading', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 4, time_cost_s: 0.45, issue: 'Late apex', tip: 'Wait longer' })]}
        isNovice={false}
      />,
    );
    expect(screen.getByText('Priority Improvements')).toBeInTheDocument();
  });

  it('shows bounded opportunity wording instead of a negative loss badge', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 4, time_cost_s: 0.45, issue: 'Late apex', tip: 'Wait longer' })]}
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
          mp({ corner: 7, time_cost_s: 0, issue: 'Turn-in timing', tip: 'Reset hands' }),
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
          mp({ corner: 3, time_cost_s: 0.5, issue: 'Late braking at corner', tip: 'Brake earlier' }),
          mp({ corner: 7, time_cost_s: 0.3, issue: 'Missing apex', tip: 'Aim tighter' }),
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
        priorities={[mp({ corner: 5, time_cost_s: 0.8, issue: 'Slow exit', tip: 'Open throttle' })]}
        isNovice={false}
      />,
    );
    expect(screen.getByText(/Explore in Deep Dive/)).toBeInTheDocument();
  });

  it('clicking "Explore" calls selectCorner, setMode, setActiveView', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 5, time_cost_s: 0.8, issue: 'Slow exit', tip: 'Open throttle' })]}
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
          mp({ corner: 1, time_cost_s: 0.3, issue: 'Entry speed', tip: 'This is a helpful tip' }),
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
          mp({ corner: 1, time_cost_s: 0.3, issue: 'Entry speed', tip: 'Hidden tip text' }),
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
          mp({ corner: 2, time_cost_s: 0.4, issue: 'Late trail brake release', tip: 'Hold longer' }),
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
          mp({ corner: 1, time_cost_s: 0.5, issue: 'Issue 1' }),
          mp({ corner: 2, time_cost_s: 0.4, issue: 'Issue 2' }),
          mp({ corner: 3, time_cost_s: 0.3, issue: 'Issue 3' }),
          mp({ corner: 4, time_cost_s: 0.2, issue: 'Issue 4' }),
        ]}
        isNovice={false}
      />,
    );
    expect(screen.getByText('Turn 1')).toBeInTheDocument();
    expect(screen.getByText('Turn 2')).toBeInTheDocument();
    expect(screen.getByText('Turn 3')).toBeInTheDocument();
    expect(screen.queryByText('Turn 4')).not.toBeInTheDocument();
  });

  it('uses time_cost_s directly from merged priority (physics source)', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 5, time_cost_s: 0.7, issue: 'Slow exit', source: 'physics', speed_gap_mph: 3.0 })]}
        isNovice={false}
      />,
    );
    // time_cost_s=0.7 -> "Up to 0.7s"
    expect(screen.getByText('Up to 0.7s')).toBeInTheDocument();
  });

  it('uses time_cost_s from merged priority (llm fallback source)', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 5, time_cost_s: 0.4, issue: 'Slow exit', source: 'llm' })]}
        isNovice={false}
      />,
    );
    expect(screen.getByText('Up to 0.4s')).toBeInTheDocument();
  });

  it('shows physics fallback tip when issue/tip is null', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 5, time_cost_s: 0.7, issue: null, tip: null, source: 'physics', speed_gap_mph: 3.2, brake_gap_m: -5 })]}
        isNovice={true}
      />,
    );
    // Fallback tip: "3.2 mph below optimal, brakes 5m early"
    expect(screen.getByText(/3\.2 mph below optimal/)).toBeInTheDocument();
    expect(screen.getByText(/brakes 5m early/)).toBeInTheDocument();
  });

  it('shows generic fallback tip when no speed gap data', () => {
    render(
      <PriorityCardsSection
        priorities={[mp({ corner: 5, time_cost_s: 0.7, issue: null, tip: null, source: 'physics' })]}
        isNovice={true}
      />,
    );
    expect(screen.getByText('Review corner data in Deep Dive')).toBeInTheDocument();
  });

  it('applies grade-based border color when cornerGrades provided', () => {
    const { container } = render(
      <PriorityCardsSection
        priorities={[
          mp({ corner: 3, time_cost_s: 0.5, issue: 'Braking too late' }),
        ]}
        isNovice={false}
        cornerGrades={[
          { corner: 3, braking: 'D', trail_braking: 'C', min_speed: 'B', throttle: 'C', notes: '' },
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
        priorities={[mp({ corner: 5, time_cost_s: 0.4, issue: 'Slow exit' })]}
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
        priorities={[mp({ corner: 5, time_cost_s: 0.6, issue: 'Slow exit' })]}
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
        priorities={[mp({ corner: 5, time_cost_s: 0.4, issue: 'Slow exit' })]}
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
        priorities={[mp({ corner: 3, time_cost_s: 0.5, issue: 'Test' })]}
        isNovice={false}
      />,
    );
    const card = container.querySelector('.border-l-\\[var\\(--cata-accent\\)\\]');
    expect(card).toBeInTheDocument();
  });
});
