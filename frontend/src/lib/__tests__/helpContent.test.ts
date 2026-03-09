import { describe, expect, it } from 'vitest';

import { helpContent } from '../help-content';

describe('helpContent', () => {
  it('describes the advanced top-3 gap metric using the implemented formula', () => {
    expect(helpContent['metric.pace-spread']).toMatch(/top 3 average minus your best lap/i);
  });

  it('frames top-priority time figures as physics-based estimates', () => {
    expect(helpContent['section.top-priorities']).toMatch(/estimate/i);
  });

  it('documents session score weighting as an ideal-lap reference with reweighted missing components', () => {
    expect(helpContent['metric.session-score']).toMatch(/ideal-lap pace reference/i);
    expect(helpContent['metric.session-score']).toMatch(/re-weighted|renormalized/i);
  });
});
