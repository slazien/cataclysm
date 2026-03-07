import { describe, expect, it } from 'vitest';

import { getPublicScoreDisplay } from './page';

describe('getPublicScoreDisplay', () => {
  it('formats public session scores on a 0-100 scale', () => {
    expect(getPublicScoreDisplay(87.6)).toEqual({
      valueText: '88',
      labelText: 'Score / 100',
    });
  });

  it('rounds down for scores just below .5', () => {
    expect(getPublicScoreDisplay(72.4)).toEqual({
      valueText: '72',
      labelText: 'Score / 100',
    });
  });

  it('handles exact integer scores', () => {
    expect(getPublicScoreDisplay(50)).toEqual({
      valueText: '50',
      labelText: 'Score / 100',
    });
  });

  it('clamps scores below 0 to 0', () => {
    expect(getPublicScoreDisplay(-10)).toEqual({
      valueText: '0',
      labelText: 'Score / 100',
    });
  });

  it('clamps scores above 100 to 100', () => {
    expect(getPublicScoreDisplay(150)).toEqual({
      valueText: '100',
      labelText: 'Score / 100',
    });
  });

  it('handles zero score', () => {
    expect(getPublicScoreDisplay(0)).toEqual({
      valueText: '0',
      labelText: 'Score / 100',
    });
  });

  it('handles score of 100', () => {
    expect(getPublicScoreDisplay(100)).toEqual({
      valueText: '100',
      labelText: 'Score / 100',
    });
  });

  it('handles very small decimal scores', () => {
    expect(getPublicScoreDisplay(0.1)).toEqual({
      valueText: '0',
      labelText: 'Score / 100',
    });
  });

  it('handles 99.9', () => {
    expect(getPublicScoreDisplay(99.9)).toEqual({
      valueText: '100',
      labelText: 'Score / 100',
    });
  });
});
