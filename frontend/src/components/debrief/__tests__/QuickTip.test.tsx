import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { QuickTip } from '../QuickTip';

// jsdom doesn't implement window.matchMedia — stub it for CornerRefLink
vi.stubGlobal(
  'matchMedia',
  vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
);

// Mock useUnits — by default resolveSpeed is a pass-through (imperial, no conversion)
const mockResolveSpeed = vi.fn((text: string) => text);

vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({ resolveSpeed: mockResolveSpeed }),
}));

// lucide-react Brain icon — keep as-is; jsdom renders SVGs fine without a special mock.

describe('QuickTip', () => {
  beforeEach(() => {
    mockResolveSpeed.mockImplementation((text: string) => text);
  });

  describe('basic rendering', () => {
    it('renders the coach tip heading', () => {
      render(<QuickTip drill="Hit the apex precisely." />);
      // The heading contains an apostrophe encoded as &apos; — match flexibly
      expect(screen.getByText(/coach'?s tip/i)).toBeInTheDocument();
    });

    it('renders the drill text', () => {
      render(<QuickTip drill="Brake smoothly at the 3-board." />);
      expect(screen.getByText('Brake smoothly at the 3-board.')).toBeInTheDocument();
    });

    it('passes the drill text through resolveSpeed', () => {
      render(<QuickTip drill="Carry {{speed:80}} through the corner." />);
      expect(mockResolveSpeed).toHaveBeenCalledWith('Carry {{speed:80}} through the corner.');
    });
  });

  describe('unit conversion integration', () => {
    it('renders the resolved text returned by resolveSpeed', () => {
      mockResolveSpeed.mockReturnValue('Carry 80 mph through the corner.');
      render(<QuickTip drill="Carry {{speed:80}} through the corner." />);
      expect(screen.getByText('Carry 80 mph through the corner.')).toBeInTheDocument();
    });

    it('renders metric text when resolveSpeed converts to km/h', () => {
      mockResolveSpeed.mockReturnValue('Carry 128.7 km/h through the corner.');
      render(<QuickTip drill="Carry {{speed:80}} through the corner." />);
      expect(screen.getByText('Carry 128.7 km/h through the corner.')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('renders the container with amber border styling', () => {
      const { container } = render(<QuickTip drill="Trail brake into T5." />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.className).toContain('border-amber-500/20');
      expect(wrapper.className).toContain('bg-amber-500/5');
    });

    it('renders the accent left border via inline style', () => {
      const { container } = render(<QuickTip drill="Trail brake into T5." />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper.style.borderLeftColor).toBe('var(--cata-accent)');
      expect(wrapper.style.borderLeftWidth).toBe('3px');
    });

    it('renders the heading with accent color class', () => {
      render(<QuickTip drill="Trail brake into T5." />);
      const heading = screen.getByText(/coach'?s tip/i);
      expect(heading.className).toContain('text-[var(--cata-accent)]');
    });
  });

  describe('Brain icon', () => {
    it('renders a Brain icon (svg) inside the component', () => {
      const { container } = render(<QuickTip drill="Some tip." />);
      // Lucide icons render as <svg> elements
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('empty drill text', () => {
    it('renders without crashing when drill is an empty string', () => {
      expect(() => render(<QuickTip drill="" />)).not.toThrow();
    });

    it('renders the heading even when drill is empty', () => {
      render(<QuickTip drill="" />);
      expect(screen.getByText(/coach'?s tip/i)).toBeInTheDocument();
    });
  });
});
