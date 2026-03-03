import { getIdentityLabel } from '../skillDimensions';

describe('getIdentityLabel', () => {
  it('returns braking label when braking is highest', () => {
    const dims = { braking: 90, trailBraking: 60, throttle: 50, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['LATE BRAKER', 'BRAKE BOSS']).toContain(label);
  });

  it('returns trail braking label when trailBraking is highest', () => {
    const dims = { braking: 50, trailBraking: 95, throttle: 60, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['TRAIL WIZARD', 'SMOOTH OPERATOR']).toContain(label);
  });

  it('returns throttle label when throttle is highest', () => {
    const dims = { braking: 50, trailBraking: 60, throttle: 92, line: 55 };
    const label = getIdentityLabel(dims);
    expect(['THROTTLE KING', 'POWER PLAYER']).toContain(label);
  });

  it('returns line label when line is highest', () => {
    const dims = { braking: 50, trailBraking: 60, throttle: 55, line: 95 };
    const label = getIdentityLabel(dims);
    expect(['LINE MASTER', 'APEX HUNTER']).toContain(label);
  });

  it('returns balanced label when all within 10pts', () => {
    const dims = { braking: 75, trailBraking: 80, throttle: 78, line: 72 };
    const label = getIdentityLabel(dims);
    expect(['COMPLETE DRIVER', 'WELL ROUNDED']).toContain(label);
  });

  it('returns fallback for null input', () => {
    expect(getIdentityLabel(null)).toBe('TRACK WARRIOR');
  });
});
