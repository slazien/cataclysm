import { describe, expect, it } from 'vitest';

import type { SessionSummary } from '@/lib/types';
import { getComparableSessions } from '../SessionSelector';

function makeSession(
  session_id: string,
  track_name: string,
  overrides?: Partial<SessionSummary>,
): SessionSummary {
  return {
    session_id,
    track_name,
    session_date: '22/02/2026 10:00',
    n_laps: 5,
    n_clean_laps: 4,
    best_lap_time_s: 90,
    top3_avg_time_s: 91,
    avg_lap_time_s: 92,
    consistency_score: 80,
    session_score: 78,
    ...overrides,
  };
}

describe('getComparableSessions', () => {
  it('keeps only same-track sessions for comparison', () => {
    const sessions = [
      makeSession('current', 'Barber Motorsports Park'),
      makeSession('same-track', 'barber motorsports park'),
      makeSession('different-track', 'Road Atlanta'),
    ];

    expect(
      getComparableSessions({
        currentSessionId: 'current',
        sessions,
        currentTrackName: 'Barber Motorsports Park',
      }).map((session) => session.session_id),
    ).toEqual(['same-track']);
  });

  it('excludes the current session from results', () => {
    const sessions = [
      makeSession('current', 'Barber Motorsports Park'),
      makeSession('other', 'Barber Motorsports Park'),
    ];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: 'Barber Motorsports Park',
    });
    expect(result.map((s) => s.session_id)).toEqual(['other']);
  });

  it('returns empty array when no other sessions match the track', () => {
    const sessions = [
      makeSession('current', 'Barber Motorsports Park'),
      makeSession('other', 'Road Atlanta'),
    ];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: 'Barber Motorsports Park',
    });
    expect(result).toEqual([]);
  });

  it('normalizes track names case-insensitively', () => {
    const sessions = [
      makeSession('current', 'BARBER MOTORSPORTS PARK'),
      makeSession('other', 'barber motorsports park'),
    ];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: 'BARBER MOTORSPORTS PARK',
    });
    expect(result.length).toBe(1);
  });

  it('normalizes track names by collapsing non-alnum chars to spaces', () => {
    const sessions = [
      makeSession('current', 'Barber-Motorsports_Park'),
      makeSession('other', 'Barber Motorsports Park'),
    ];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: 'Barber-Motorsports_Park',
    });
    expect(result.length).toBe(1);
  });

  it('handles null currentTrackName gracefully', () => {
    const sessions = [makeSession('current', ''), makeSession('other', '')];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: null,
    });
    // Empty strings match empty normalized name
    expect(result.length).toBe(1);
  });

  it('handles undefined currentTrackName gracefully', () => {
    const sessions = [makeSession('current', ''), makeSession('other', '')];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: undefined,
    });
    expect(result.length).toBe(1);
  });

  it('returns multiple sessions when multiple same-track sessions exist', () => {
    const sessions = [
      makeSession('current', 'Barber'),
      makeSession('s1', 'Barber'),
      makeSession('s2', 'barber'),
      makeSession('s3', 'Road Atlanta'),
    ];

    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions,
      currentTrackName: 'Barber',
    });
    expect(result.length).toBe(2);
    expect(result.map((s) => s.session_id).sort()).toEqual(['s1', 's2']);
  });

  it('returns empty array when sessions list is empty', () => {
    const result = getComparableSessions({
      currentSessionId: 'current',
      sessions: [],
      currentTrackName: 'Barber',
    });
    expect(result).toEqual([]);
  });
});
