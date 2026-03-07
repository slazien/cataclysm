import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import PublicViewPage from './page';

const mockUseQuery = vi.fn();

vi.mock('next/navigation', () => ({
  useParams: () => ({ token: 'test-token-123' }),
}));

vi.mock('@tanstack/react-query', () => ({
  useQuery: (opts: unknown) => mockUseQuery(opts),
}));

vi.mock('@/lib/api', () => ({
  getPublicSessionView: vi.fn(),
}));

vi.mock('@/components/shared/RadarChart', () => ({
  RadarChart: ({ axes, size }: { axes: string[]; size?: number }) => (
    <div data-testid="radar-chart" data-axes={axes.join(',')} />
  ),
}));

vi.mock('@/components/shared/TrackOutlineSVG', () => ({
  TrackOutlineSVG: ({ className }: { className?: string }) => (
    <div data-testid="track-outline" className={className} />
  ),
}));

vi.mock('@/components/shared/SignUpCTA', () => ({
  SignUpCTA: () => <div data-testid="signup-cta" />,
}));

vi.mock('lucide-react', () => ({
  AlertCircle: ({ className }: { className?: string }) => (
    <svg data-testid="alert-circle" className={className} />
  ),
  Loader2: ({ className }: { className?: string }) => (
    <svg data-testid="loader" className={className} />
  ),
  Trophy: ({ className }: { className?: string }) => (
    <svg data-testid="trophy" className={className} />
  ),
  Gauge: ({ className }: { className?: string }) => (
    <svg data-testid="gauge" className={className} />
  ),
  Target: ({ className }: { className?: string }) => (
    <svg data-testid="target" className={className} />
  ),
  Timer: ({ className }: { className?: string }) => (
    <svg data-testid="timer" className={className} />
  ),
}));

describe('PublicViewPage', () => {
  beforeEach(() => {
    mockUseQuery.mockReset();
  });

  it('renders loading state', () => {
    mockUseQuery.mockReturnValue({ data: undefined, isLoading: true, error: null });
    render(<PublicViewPage />);
    expect(screen.getByTestId('loader')).toBeInTheDocument();
    expect(screen.getByText('Loading session...')).toBeInTheDocument();
  });

  it('renders error/not-found state when error occurs', () => {
    mockUseQuery.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Not found'),
    });
    render(<PublicViewPage />);
    expect(screen.getByText('Session Not Found')).toBeInTheDocument();
    expect(
      screen.getByText('This session link is invalid or has been removed.'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('signup-cta')).toBeInTheDocument();
  });

  it('renders error/not-found state when data is null', () => {
    mockUseQuery.mockReturnValue({ data: null, isLoading: false, error: null });
    render(<PublicViewPage />);
    expect(screen.getByText('Session Not Found')).toBeInTheDocument();
  });

  it('renders expired state', () => {
    mockUseQuery.mockReturnValue({
      data: {
        token: 'test-token-123',
        track_name: 'Barber',
        session_date: '2026-03-01',
        driver_name: 'John',
        is_expired: true,
        best_lap_time_s: null,
        n_laps: null,
        consistency_score: null,
        session_score: null,
        top_speed_mph: null,
        skill_braking: null,
        skill_trail_braking: null,
        skill_throttle: null,
        skill_line: null,
        coaching_summary: null,
        track_coords: null,
      },
      isLoading: false,
      error: null,
    });
    render(<PublicViewPage />);
    expect(screen.getByText('Session Link Expired')).toBeInTheDocument();
    expect(screen.getByText('This session link has expired.')).toBeInTheDocument();
    expect(screen.getByTestId('signup-cta')).toBeInTheDocument();
  });

  it('renders full session data with all stats', () => {
    mockUseQuery.mockReturnValue({
      data: {
        token: 'test-token-123',
        track_name: 'Barber Motorsports Park',
        session_date: '2026-03-01',
        driver_name: 'John Doe',
        is_expired: false,
        best_lap_time_s: 85.5,
        n_laps: 12,
        consistency_score: 87,
        session_score: 82,
        top_speed_mph: 120,
        skill_braking: 75,
        skill_trail_braking: 60,
        skill_throttle: 80,
        skill_line: 70,
        coaching_summary: 'Great session with room to improve braking.',
        track_coords: null,
      },
      isLoading: false,
      error: null,
    });
    render(<PublicViewPage />);

    // Header
    expect(screen.getByText('Barber Motorsports Park')).toBeInTheDocument();
    // The driver name and date are in the same <p> with middot separator
    expect(screen.getByText(/John Doe/)).toBeInTheDocument();

    // Best lap time
    expect(screen.getByText('Best Lap')).toBeInTheDocument();

    // Consistency
    expect(screen.getByText('87%')).toBeInTheDocument();
    expect(screen.getByText('Consistency')).toBeInTheDocument();

    // Session score
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.getByText('Score / 100')).toBeInTheDocument();

    // Top speed
    expect(screen.getByText('120 mph')).toBeInTheDocument();
    expect(screen.getByText('Top Speed')).toBeInTheDocument();

    // Skill radar
    expect(screen.getByTestId('radar-chart')).toBeInTheDocument();
    expect(screen.getByText('Skill Profile')).toBeInTheDocument();

    // Coaching summary
    expect(
      screen.getByText('Great session with room to improve braking.'),
    ).toBeInTheDocument();
    expect(screen.getByText('AI Coaching Summary')).toBeInTheDocument();

    // CTA
    expect(screen.getByTestId('signup-cta')).toBeInTheDocument();
  });

  it('renders track outline when track_coords has 10+ points', () => {
    const lat = Array.from({ length: 20 }, (_, i) => 33.5 + i * 0.001);
    const lon = Array.from({ length: 20 }, (_, i) => -86.6 + i * 0.001);
    mockUseQuery.mockReturnValue({
      data: {
        token: 'test-token-123',
        track_name: 'Barber',
        session_date: '2026-03-01',
        driver_name: 'John',
        is_expired: false,
        best_lap_time_s: 85,
        n_laps: 10,
        consistency_score: null,
        session_score: null,
        top_speed_mph: null,
        skill_braking: null,
        skill_trail_braking: null,
        skill_throttle: null,
        skill_line: null,
        coaching_summary: null,
        track_coords: { lat, lon },
      },
      isLoading: false,
      error: null,
    });
    render(<PublicViewPage />);
    expect(screen.getByTestId('track-outline')).toBeInTheDocument();
  });

  it('does not render track outline when coords have fewer than 10 points', () => {
    mockUseQuery.mockReturnValue({
      data: {
        token: 'test-token-123',
        track_name: 'Barber',
        session_date: '2026-03-01',
        driver_name: 'John',
        is_expired: false,
        best_lap_time_s: 85,
        n_laps: 10,
        consistency_score: null,
        session_score: null,
        top_speed_mph: null,
        skill_braking: null,
        skill_trail_braking: null,
        skill_throttle: null,
        skill_line: null,
        coaching_summary: null,
        track_coords: { lat: [1, 2, 3], lon: [4, 5, 6] },
      },
      isLoading: false,
      error: null,
    });
    render(<PublicViewPage />);
    expect(screen.queryByTestId('track-outline')).not.toBeInTheDocument();
  });

  it('hides stats cards when values are null', () => {
    mockUseQuery.mockReturnValue({
      data: {
        token: 'test-token-123',
        track_name: 'Barber',
        session_date: '2026-03-01',
        driver_name: 'John',
        is_expired: false,
        best_lap_time_s: null,
        n_laps: null,
        consistency_score: null,
        session_score: null,
        top_speed_mph: null,
        skill_braking: null,
        skill_trail_braking: null,
        skill_throttle: null,
        skill_line: null,
        coaching_summary: null,
        track_coords: null,
      },
      isLoading: false,
      error: null,
    });
    render(<PublicViewPage />);
    expect(screen.queryByText('Best Lap')).not.toBeInTheDocument();
    expect(screen.queryByText('Consistency')).not.toBeInTheDocument();
    expect(screen.queryByText('Score / 100')).not.toBeInTheDocument();
    expect(screen.queryByText('Top Speed')).not.toBeInTheDocument();
    expect(screen.queryByTestId('radar-chart')).not.toBeInTheDocument();
    expect(screen.queryByText('AI Coaching Summary')).not.toBeInTheDocument();
  });

  it('hides skill radar when not all skills are present', () => {
    mockUseQuery.mockReturnValue({
      data: {
        token: 'test-token-123',
        track_name: 'Barber',
        session_date: '2026-03-01',
        driver_name: 'John',
        is_expired: false,
        best_lap_time_s: 85,
        n_laps: 10,
        consistency_score: null,
        session_score: null,
        top_speed_mph: null,
        skill_braking: 80,
        skill_trail_braking: 70,
        skill_throttle: null, // missing
        skill_line: 60,
        coaching_summary: null,
        track_coords: null,
      },
      isLoading: false,
      error: null,
    });
    render(<PublicViewPage />);
    expect(screen.queryByTestId('radar-chart')).not.toBeInTheDocument();
  });

  it('passes correct queryFn that calls getPublicSessionView with token', async () => {
    const { getPublicSessionView } = await import('@/lib/api');
    const mockGetPublicSessionView = vi.mocked(getPublicSessionView);
    mockGetPublicSessionView.mockResolvedValue({} as ReturnType<typeof getPublicSessionView> extends Promise<infer T> ? T : never);

    let capturedOpts: { queryFn?: () => unknown; queryKey?: unknown[]; enabled?: boolean } = {};
    mockUseQuery.mockImplementation((opts: typeof capturedOpts) => {
      capturedOpts = opts;
      return { data: undefined, isLoading: true, error: null };
    });

    render(<PublicViewPage />);

    // The queryFn should be defined and call getPublicSessionView with the token
    expect(capturedOpts.queryFn).toBeDefined();
    expect(capturedOpts.queryKey).toEqual(['public-view', 'test-token-123']);
    expect(capturedOpts.enabled).toBe(true);

    // Call the queryFn to exercise line 25
    capturedOpts.queryFn!();
    expect(mockGetPublicSessionView).toHaveBeenCalledWith('test-token-123');
  });
});
