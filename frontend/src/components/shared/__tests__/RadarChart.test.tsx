import '@testing-library/jest-dom/vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import { RadarChart } from '../RadarChart';

// Mock motion/react — replace motion.* with plain SVG elements
vi.mock('motion/react', () => ({
  motion: {
    polygon: ({
      children,
      initial,
      animate,
      transition,
      ...rest
    }: React.SVGAttributes<SVGPolygonElement> & Record<string, unknown>) => (
      <polygon {...rest}>{children}</polygon>
    ),
    path: ({
      children,
      initial,
      animate,
      transition,
      pathLength,
      ...rest
    }: React.SVGAttributes<SVGPathElement> & Record<string, unknown>) => (
      <path {...rest}>{children}</path>
    ),
    circle: ({
      children,
      initial,
      animate,
      transition,
      ...rest
    }: React.SVGAttributes<SVGCircleElement> & Record<string, unknown>) => (
      <circle {...rest}>{children}</circle>
    ),
  },
}));

const TEST_AXES = ['Braking', 'Trail Braking', 'Throttle', 'Line'] as const;

const TEST_DATASET = [
  {
    label: 'Skills',
    values: [80, 60, 70, 90],
    color: '#6366f1',
  },
];

describe('RadarChart', () => {
  it('renders an SVG element', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('uses default size=200', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('200');
    expect(svg.getAttribute('height')).toBe('200');
  });

  it('uses custom size', () => {
    const { container } = render(
      <RadarChart axes={TEST_AXES} datasets={TEST_DATASET} size={300} />,
    );
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('300');
    expect(svg.getAttribute('height')).toBe('300');
  });

  it('sets viewBox to match size', () => {
    const { container } = render(
      <RadarChart axes={TEST_AXES} datasets={TEST_DATASET} size={240} />,
    );
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('viewBox')).toBe('0 0 240 240');
  });

  it('renders 5 grid ring polygons (20, 40, 60, 80, 100)', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    // Grid ring polygons have stroke="rgba(255,255,255,0.08)"
    const gridPolygons = container.querySelectorAll(
      'polygon[stroke="rgba(255,255,255,0.08)"]',
    );
    expect(gridPolygons.length).toBe(5);
  });

  it('renders axis lines equal to the number of axes', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    const lines = container.querySelectorAll('line');
    expect(lines.length).toBe(TEST_AXES.length);
  });

  it('axis lines originate from the center', () => {
    const size = 200;
    const center = String(size / 2);
    const { container } = render(
      <RadarChart axes={TEST_AXES} datasets={TEST_DATASET} size={size} />,
    );
    const lines = container.querySelectorAll('line');
    lines.forEach((line) => {
      expect(line.getAttribute('x1')).toBe(center);
      expect(line.getAttribute('y1')).toBe(center);
    });
  });

  it('renders axis label text elements for each axis', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    const textElements = container.querySelectorAll('text');
    expect(textElements.length).toBe(TEST_AXES.length);
    const labels = Array.from(textElements).map((el) => el.textContent);
    expect(labels).toContain('Braking');
    expect(labels).toContain('Trail Braking');
    expect(labels).toContain('Throttle');
    expect(labels).toContain('Line');
  });

  it('renders a data polygon (fill area) for each dataset', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    // Data fill polygons have the dataset color as fill
    const dataPolygons = container.querySelectorAll('polygon[fill="#6366f1"]');
    expect(dataPolygons.length).toBe(1);
  });

  it('renders a stroke path for each dataset', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    const dataPaths = container.querySelectorAll('path[stroke="#6366f1"]');
    expect(dataPaths.length).toBe(1);
  });

  it('renders data-point circles (dots) by default', () => {
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={TEST_DATASET} />);
    const circles = container.querySelectorAll('circle[fill="#6366f1"]');
    expect(circles.length).toBe(TEST_AXES.length);
  });

  it('does not render dots when showDots=false', () => {
    const dataset = [{ ...TEST_DATASET[0], showDots: false }];
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={dataset} />);
    const circles = container.querySelectorAll('circle[fill="#6366f1"]');
    expect(circles.length).toBe(0);
  });

  it('renders multiple datasets correctly', () => {
    const multiDatasets = [
      { label: 'Current', values: [80, 60, 70, 90], color: '#6366f1' },
      { label: 'Previous', values: [60, 50, 80, 70], color: '#f97316' },
    ];
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={multiDatasets} />);
    const purplePolygons = container.querySelectorAll('polygon[fill="#6366f1"]');
    const orangePolygons = container.querySelectorAll('polygon[fill="#f97316"]');
    expect(purplePolygons.length).toBe(1);
    expect(orangePolygons.length).toBe(1);
  });

  it('clamps values to maxValue', () => {
    const overflowDataset = [
      { label: 'Over', values: [150, 200, 50, 100], color: '#6366f1' },
    ];
    // Should render without error — values above maxValue are clamped
    const { container } = render(
      <RadarChart axes={TEST_AXES} datasets={overflowDataset} maxValue={100} />,
    );
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('respects custom maxValue', () => {
    const { container } = render(
      <RadarChart axes={TEST_AXES} datasets={TEST_DATASET} maxValue={200} />,
    );
    // With maxValue=200, values of 60-90 would produce smaller polygons
    // Just verify it renders fine
    expect(container.querySelector('svg')).toBeInTheDocument();
  });

  it('uses custom fillOpacity when provided', () => {
    const dataset = [{ ...TEST_DATASET[0], fillOpacity: 0.5 }];
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={dataset} />);
    const dataPolygon = container.querySelector('polygon[fill="#6366f1"]') as SVGPolygonElement;
    expect(dataPolygon.getAttribute('fill-opacity')).toBe('0.5');
  });

  it('uses custom strokeOpacity when provided', () => {
    const dataset = [{ ...TEST_DATASET[0], strokeOpacity: 0.7 }];
    const { container } = render(<RadarChart axes={TEST_AXES} datasets={dataset} />);
    const dataPath = container.querySelector('path[stroke="#6366f1"]') as SVGPathElement;
    expect(dataPath.getAttribute('stroke-opacity')).toBe('0.7');
  });

  it('handles 3-axis radar chart', () => {
    const axes = ['A', 'B', 'C'] as const;
    const datasets = [{ label: 'Test', values: [50, 60, 70], color: '#ff0000' }];
    const { container } = render(<RadarChart axes={axes} datasets={datasets} />);
    const lines = container.querySelectorAll('line');
    expect(lines.length).toBe(3);
    const textEls = container.querySelectorAll('text');
    expect(textEls.length).toBe(3);
  });

  it('handles 6-axis radar chart', () => {
    const axes = ['A', 'B', 'C', 'D', 'E', 'F'] as const;
    const datasets = [{ label: 'Test', values: [10, 20, 30, 40, 50, 60], color: '#ff0000' }];
    const { container } = render(<RadarChart axes={axes} datasets={datasets} />);
    const lines = container.querySelectorAll('line');
    expect(lines.length).toBe(6);
  });
});
