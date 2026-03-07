import '@testing-library/jest-dom/vitest';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { TrackOutlineSVG } from '../TrackOutlineSVG';

// Generate enough coords for a valid track (>= 10 points)
function makeCoords(n: number) {
  const lat: number[] = [];
  const lon: number[] = [];
  for (let i = 0; i < n; i++) {
    const angle = (2 * Math.PI * i) / n;
    lat.push(33.5 + 0.01 * Math.sin(angle));
    lon.push(-86.6 + 0.01 * Math.cos(angle));
  }
  return { lat, lon };
}

describe('TrackOutlineSVG', () => {
  it('renders nothing when coords have fewer than 10 points', () => {
    const { container } = render(
      <TrackOutlineSVG coords={{ lat: [1, 2, 3], lon: [4, 5, 6] }} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders nothing when coords have exactly 9 points', () => {
    const coords = makeCoords(9);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders an SVG element when coords have 10+ points', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('uses default width=400 and height=300', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('400');
    expect(svg.getAttribute('height')).toBe('300');
  });

  it('uses custom width and height', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} width={600} height={400} />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('600');
    expect(svg.getAttribute('height')).toBe('400');
  });

  it('sets the viewBox to match width and height', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} width={500} height={350} />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('viewBox')).toBe('0 0 500 350');
  });

  it('renders a path element for the track outline', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const path = container.querySelector('path');
    expect(path).toBeInTheDocument();
  });

  it('path starts with M and ends with Z', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const path = container.querySelector('path')!;
    const d = path.getAttribute('d')!;
    expect(d).toMatch(/^M/);
    expect(d).toMatch(/Z$/);
  });

  it('path has correct stroke color (#6366f1)', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const path = container.querySelector('path')!;
    expect(path.getAttribute('stroke')).toBe('#6366f1');
  });

  it('path has fill=none', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const path = container.querySelector('path')!;
    expect(path.getAttribute('fill')).toBe('none');
  });

  it('renders a filter definition for the glow effect', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} />);
    const filter = container.querySelector('filter');
    expect(filter).toBeInTheDocument();
  });

  it('applies className to the SVG', () => {
    const coords = makeCoords(20);
    const { container } = render(<TrackOutlineSVG coords={coords} className="opacity-60" />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('class')).toContain('opacity-60');
  });

  it('handles coords where all lat values are the same (zero range)', () => {
    const lat = Array(15).fill(33.5);
    const lon = Array.from({ length: 15 }, (_, i) => -86.6 + i * 0.001);
    const { container } = render(<TrackOutlineSVG coords={{ lat, lon }} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('handles coords where all lon values are the same (zero range)', () => {
    const lat = Array.from({ length: 15 }, (_, i) => 33.5 + i * 0.001);
    const lon = Array(15).fill(-86.6);
    const { container } = render(<TrackOutlineSVG coords={{ lat, lon }} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });
});
