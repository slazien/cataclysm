import '@testing-library/jest-dom/vitest';
import { render, act } from '@testing-library/react';
import { CircularProgress } from '../CircularProgress';

// jsdom does not implement requestAnimationFrame — provide a minimal stub that
// does NOT call the callback synchronously to prevent the recursive loop:
// CircularProgress's tick() calls setIndeterminate() then schedules another RAF.
// If we invoke cb() immediately it causes unlimited React state updates.
// Instead we store pending callbacks and let tests control when they fire.
let rafCallbacks: Map<number, FrameRequestCallback> = new Map();
let rafIdCounter = 0;

beforeAll(() => {
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback): number => {
    const id = ++rafIdCounter;
    rafCallbacks.set(id, cb);
    return id;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => {
    rafCallbacks.delete(id);
  });
});

beforeEach(() => {
  rafCallbacks = new Map();
  rafIdCounter = 0;
});

afterAll(() => {
  vi.unstubAllGlobals();
});

/** Extract the progress <circle> (second circle) from the rendered SVG. */
function getProgressCircle(container: HTMLElement): SVGCircleElement {
  const circles = container.querySelectorAll('circle');
  // circles[0] = background track, circles[1] = progress arc
  return circles[1] as SVGCircleElement;
}

/** Extract the background track <circle> from the rendered SVG. */
function getTrackCircle(container: HTMLElement): SVGCircleElement {
  return container.querySelectorAll('circle')[0] as SVGCircleElement;
}

describe('CircularProgress', () => {
  describe('SVG element', () => {
    it('renders an SVG element', () => {
      const { container } = render(<CircularProgress progress={50} />);
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('uses the provided size for width and height', () => {
      const { container } = render(<CircularProgress progress={50} size={40} />);
      const svg = container.querySelector('svg')!;
      expect(svg.getAttribute('width')).toBe('40');
      expect(svg.getAttribute('height')).toBe('40');
    });

    it('defaults to size 20 when size is not provided', () => {
      const { container } = render(<CircularProgress progress={50} />);
      const svg = container.querySelector('svg')!;
      expect(svg.getAttribute('width')).toBe('20');
      expect(svg.getAttribute('height')).toBe('20');
    });
  });

  describe('determinate mode', () => {
    it('renders two circles (track and progress arc)', () => {
      const { container } = render(<CircularProgress progress={50} />);
      expect(container.querySelectorAll('circle').length).toBe(2);
    });

    it('computes correct strokeDashoffset for 0%', () => {
      const size = 20;
      const strokeWidth = 2.5;
      const radius = (size - strokeWidth) / 2;
      const circumference = 2 * Math.PI * radius;

      const { container } = render(<CircularProgress progress={0} size={size} strokeWidth={strokeWidth} />);
      const progressCircle = getProgressCircle(container);
      const offset = parseFloat(progressCircle.getAttribute('stroke-dashoffset')!);
      expect(offset).toBeCloseTo(circumference, 5);
    });

    it('computes correct strokeDashoffset for 100%', () => {
      const { container } = render(<CircularProgress progress={100} />);
      const progressCircle = getProgressCircle(container);
      const offset = parseFloat(progressCircle.getAttribute('stroke-dashoffset')!);
      expect(offset).toBeCloseTo(0, 5);
    });

    it('computes correct strokeDashoffset for 50%', () => {
      const size = 20;
      const strokeWidth = 2.5;
      const radius = (size - strokeWidth) / 2;
      const circumference = 2 * Math.PI * radius;

      const { container } = render(<CircularProgress progress={50} size={size} strokeWidth={strokeWidth} />);
      const progressCircle = getProgressCircle(container);
      const offset = parseFloat(progressCircle.getAttribute('stroke-dashoffset')!);
      expect(offset).toBeCloseTo(circumference / 2, 5);
    });

    it('clamps progress below 0 to 0%', () => {
      const size = 20;
      const strokeWidth = 2.5;
      const radius = (size - strokeWidth) / 2;
      const circumference = 2 * Math.PI * radius;

      const { container } = render(<CircularProgress progress={-10} size={size} strokeWidth={strokeWidth} />);
      const progressCircle = getProgressCircle(container);
      const offset = parseFloat(progressCircle.getAttribute('stroke-dashoffset')!);
      expect(offset).toBeCloseTo(circumference, 5);
    });

    it('clamps progress above 100 to 100%', () => {
      const { container } = render(<CircularProgress progress={150} />);
      const progressCircle = getProgressCircle(container);
      const offset = parseFloat(progressCircle.getAttribute('stroke-dashoffset')!);
      expect(offset).toBeCloseTo(0, 5);
    });

    it('applies a CSS transition on the progress arc in determinate mode', () => {
      const { container } = render(<CircularProgress progress={75} />);
      const progressCircle = getProgressCircle(container);
      expect((progressCircle as HTMLElement).style.transition).toContain('stroke-dashoffset');
    });
  });

  describe('indeterminate mode', () => {
    it('renders when progress prop is omitted', async () => {
      let container!: HTMLElement;
      await act(async () => {
        ({ container } = render(<CircularProgress />));
      });
      expect(container.querySelector('svg')).toBeInTheDocument();
    });

    it('does not apply a CSS transition on the progress arc in indeterminate mode', async () => {
      let container!: HTMLElement;
      await act(async () => {
        ({ container } = render(<CircularProgress />));
      });
      const progressCircle = getProgressCircle(container);
      // In indeterminate mode the component sets transition: 'none'
      expect((progressCircle as HTMLElement).style.transition).toBe('none');
    });
  });

  describe('color props', () => {
    it('uses the provided color for the progress arc stroke', () => {
      const { container } = render(<CircularProgress progress={50} color="#ff0000" />);
      const progressCircle = getProgressCircle(container);
      expect(progressCircle.getAttribute('stroke')).toBe('#ff0000');
    });

    it('uses the provided trackColor for the background track stroke', () => {
      const { container } = render(<CircularProgress progress={50} trackColor="#cccccc" />);
      const trackCircle = getTrackCircle(container);
      expect(trackCircle.getAttribute('stroke')).toBe('#cccccc');
    });

    it('defaults to var(--cata-accent) for the progress arc color', () => {
      const { container } = render(<CircularProgress progress={50} />);
      const progressCircle = getProgressCircle(container);
      expect(progressCircle.getAttribute('stroke')).toBe('var(--cata-accent)');
    });
  });

  describe('className prop', () => {
    it('applies a custom className to the SVG element', () => {
      const { container } = render(<CircularProgress progress={50} className="animate-spin" />);
      const svg = container.querySelector('svg')!;
      expect(svg.className.baseVal).toContain('animate-spin');
    });
  });
});
