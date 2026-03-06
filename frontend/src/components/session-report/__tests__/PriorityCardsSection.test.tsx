import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { PriorityCardsSection } from '../PriorityCardsSection';

vi.mock('@/stores', () => ({
  useUiStore: (selector: (state: { setActiveView: () => void }) => unknown) =>
    selector({ setActiveView: vi.fn() }),
  useAnalysisStore: (
    selector: (state: { setMode: () => void; selectCorner: () => void }) => unknown,
  ) => selector({ setMode: vi.fn(), selectCorner: vi.fn() }),
}));

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({ resolveSpeed: (text: string) => text }),
}));

vi.mock('@/components/shared/MarkdownText', () => ({
  MarkdownText: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

describe('PriorityCardsSection', () => {
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
        priorities={[{ corner: 7, time_cost_s: 0, issue: 'Turn-in timing', tip: 'Reset hands' }]}
        isNovice={false}
      />,
    );

    expect(screen.getByText('Estimate unavailable')).toBeTruthy();
  });
});
