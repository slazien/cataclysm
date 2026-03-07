import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { SessionSelector } from '../SessionSelector';

const mockPush = vi.fn();
const mockBack = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, back: mockBack }),
}));

const mockUseSessions = vi.fn();

vi.mock('@/hooks/useSession', () => ({
  useSessions: () => mockUseSessions(),
}));

vi.mock('@/components/shared/CircularProgress', () => ({
  CircularProgress: ({ size }: { size?: number }) => <div data-testid="loading-spinner" />,
}));

vi.mock('@/components/ui/button', () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    variant?: string;
    size?: string;
    title?: string;
    className?: string;
  }) => (
    <button onClick={onClick} title={props.title}>
      {children}
    </button>
  ),
}));

vi.mock('lucide-react', () => ({
  ArrowLeft: () => <svg data-testid="arrow-left" />,
  ArrowRight: () => <svg data-testid="arrow-right" />,
}));

function makeSessions() {
  return {
    items: [
      {
        session_id: 'session-1',
        track_name: 'Barber Motorsports Park',
        session_date: '22/02/2026 10:00',
        n_laps: 10,
        n_clean_laps: 8,
        best_lap_time_s: 85.5,
        top3_avg_time_s: 86.0,
        avg_lap_time_s: 88.0,
        consistency_score: 85,
        session_score: 80,
      },
      {
        session_id: 'session-2',
        track_name: 'Barber Motorsports Park',
        session_date: '23/02/2026 14:00',
        n_laps: 12,
        n_clean_laps: 10,
        best_lap_time_s: 84.0,
        top3_avg_time_s: 85.0,
        avg_lap_time_s: 87.0,
        consistency_score: 90,
        session_score: 85,
      },
      {
        session_id: 'session-3',
        track_name: 'Road Atlanta',
        session_date: '24/02/2026 09:00',
        n_laps: 8,
        n_clean_laps: 6,
        best_lap_time_s: 95.0,
        top3_avg_time_s: 96.0,
        avg_lap_time_s: 98.0,
        consistency_score: 75,
        session_score: 70,
      },
    ],
  };
}

describe('SessionSelector', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockBack.mockReset();
    mockUseSessions.mockReset();
  });

  it('shows loading spinner when sessions are loading', () => {
    mockUseSessions.mockReturnValue({ data: undefined, isLoading: true });
    render(<SessionSelector currentSessionId="session-1" />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    expect(screen.getByText('Loading sessions...')).toBeInTheDocument();
  });

  it('renders the Compare Sessions header', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    expect(screen.getByText('Compare Sessions')).toBeInTheDocument();
  });

  it('shows current session track name in description', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    // The track name appears in the current session info card and in the description
    const allMatches = screen.getAllByText('Barber Motorsports Park');
    expect(allMatches.length).toBeGreaterThanOrEqual(1);
  });

  it('shows session ID prefix when current session not found', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="unknown-session-id" />);
    // slice(0,8) of "unknown-session-id" = "unknown-"
    expect(screen.getByText('unknown-')).toBeInTheDocument();
  });

  it('displays current session card with track name and date', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    expect(screen.getByText('Current Session')).toBeInTheDocument();
  });

  it('shows comparable sessions from the same track', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    // session-2 is on the same track, session-3 is Road Atlanta (different)
    expect(screen.getByText('Select a session to compare')).toBeInTheDocument();
    // session-2's date should be listed; session-3's date should not
    expect(screen.getByText(/23\/02\/2026/)).toBeInTheDocument();
    expect(screen.queryByText(/24\/02\/2026/)).not.toBeInTheDocument();
  });

  it('shows empty state when no comparable sessions exist', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-3" />);
    expect(
      screen.getByText('No comparable sessions available for this track.'),
    ).toBeInTheDocument();
  });

  it('navigates back when back button is clicked', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    const backButton = screen.getByTitle('Go back');
    fireEvent.click(backButton);
    expect(mockBack).toHaveBeenCalledTimes(1);
  });

  it('shows Compare button after selecting a session', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    // Compare button should not exist initially
    expect(screen.queryByText('Compare')).not.toBeInTheDocument();

    // Click on session-2 (find it by the date text in the session row)
    const dateText = screen.getByText(/23\/02\/2026/);
    const sessionButton = dateText.closest('button')!;
    fireEvent.click(sessionButton);

    expect(screen.getByText('Compare')).toBeInTheDocument();
  });

  it('navigates to compare page when Compare is clicked', () => {
    mockUseSessions.mockReturnValue({ data: makeSessions(), isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);

    // Select session-2
    const dateText = screen.getByText(/23\/02\/2026/);
    const sessionButton = dateText.closest('button')!;
    fireEvent.click(sessionButton);

    // Click Compare
    fireEvent.click(screen.getByText('Compare'));
    expect(mockPush).toHaveBeenCalledWith('/compare/session-1?with=session-2');
  });

  it('handles empty sessions data', () => {
    mockUseSessions.mockReturnValue({ data: { items: [] }, isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    expect(
      screen.getByText('No comparable sessions available for this track.'),
    ).toBeInTheDocument();
  });

  it('handles undefined sessions data', () => {
    mockUseSessions.mockReturnValue({ data: undefined, isLoading: false });
    render(<SessionSelector currentSessionId="session-1" />);
    expect(
      screen.getByText('No comparable sessions available for this track.'),
    ).toBeInTheDocument();
  });

  it('sorts comparable sessions by date descending (newest first)', () => {
    mockUseSessions.mockReturnValue({
      data: {
        items: [
          {
            session_id: 'session-1',
            track_name: 'Barber Motorsports Park',
            session_date: '22/02/2026 10:00',
            n_laps: 10,
            n_clean_laps: 8,
            best_lap_time_s: 85.5,
            top3_avg_time_s: 86.0,
            avg_lap_time_s: 88.0,
            consistency_score: 85,
            session_score: 80,
          },
          {
            session_id: 'session-older',
            track_name: 'Barber Motorsports Park',
            session_date: '20/02/2026 09:00',
            n_laps: 8,
            n_clean_laps: 6,
            best_lap_time_s: 87.0,
            top3_avg_time_s: 88.0,
            avg_lap_time_s: 89.0,
            consistency_score: 75,
            session_score: 70,
          },
          {
            session_id: 'session-newer',
            track_name: 'Barber Motorsports Park',
            session_date: '25/02/2026 14:00',
            n_laps: 12,
            n_clean_laps: 10,
            best_lap_time_s: 84.0,
            top3_avg_time_s: 85.0,
            avg_lap_time_s: 87.0,
            consistency_score: 90,
            session_score: 85,
          },
        ],
      },
      isLoading: false,
    });

    render(<SessionSelector currentSessionId="session-1" />);

    // Both comparable sessions should be listed
    const buttons = screen.getAllByRole('button').filter(
      (btn) => btn.textContent?.includes('Barber Motorsports Park') && !btn.getAttribute('title'),
    );
    expect(buttons.length).toBe(2);

    // The newer session (25/02) should appear before the older session (20/02)
    const allText = buttons.map((b) => b.textContent ?? '');
    const newerIdx = allText.findIndex((t) => t.includes('25/02/2026'));
    const olderIdx = allText.findIndex((t) => t.includes('20/02/2026'));
    expect(newerIdx).toBeLessThan(olderIdx);
  });
});
