import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { MetricsGrid } from '../MetricsGrid';

vi.mock('@/components/shared/InfoTooltip', () => ({
  InfoTooltip: () => <span data-testid="info-tooltip" />,
}));

describe('MetricsGrid', () => {
  it('labels the advanced pace delta as the top-3 gap it actually computes', () => {
    render(
      <MetricsGrid
        session={{
          session_id: 'sess-1',
          track_name: 'Barber',
          session_date: '2026-02-22',
          n_laps: 8,
          n_clean_laps: 6,
          best_lap_time_s: 100,
          top3_avg_time_s: 100.3,
          avg_lap_time_s: 101,
          consistency_score: 82,
          session_score: 78,
        }}
        laps={[]}
        consistency={null}
        isNovice={false}
        isAdvanced
      />,
    );

    expect(screen.getByText('Top 3 Gap')).toBeTruthy();
    expect(screen.queryByText('Pace Spread')).toBeNull();
  });

  it('prefers physics-optimal lap time over session ideal lap', () => {
    render(
      <MetricsGrid
        session={{
          session_id: 'sess-1',
          track_name: 'Barber',
          session_date: '2026-02-22',
          n_laps: 8,
          n_clean_laps: 6,
          best_lap_time_s: 100,
          top3_avg_time_s: 100.3,
          avg_lap_time_s: 101,
          consistency_score: 82,
          session_score: 78,
          optimal_lap_time_s: 98.5,
        }}
        laps={[]}
        consistency={null}
        isNovice={false}
        isAdvanced={false}
        physicsOptimalLapTime={96.2}
      />,
    );

    // Should show physics-optimal (1:36.200), not session ideal (1:38.500)
    expect(screen.getByText('1:36.200')).toBeTruthy();
    expect(screen.queryByText('1:38.500')).toBeNull();
  });
});
