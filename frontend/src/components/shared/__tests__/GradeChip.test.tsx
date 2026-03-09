import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GradeChip } from '../GradeChip';

// GradeChip uses motion/react for entrance animation — replace with plain elements
vi.mock('motion/react', () => ({
  motion: {
    span: ({ children, className, ...rest }: React.HTMLAttributes<HTMLSpanElement>) => (
      <span className={className} {...rest}>
        {children}
      </span>
    ),
  },
}));

// design-tokens motion export is only referenced for transition config — no-op is fine
vi.mock('@/lib/design-tokens', () => ({
  motion: { gradeChip: {} },
  colors: {
    lap: ['#58a6ff'],
    comparison: { reference: '#58a6ff', compare: '#f97316' },
  },
}));

// useUnits — default imperial (isMetric: false)
vi.mock('@/hooks/useUnits', () => ({
  useUnits: () => ({ isMetric: false }),
}));

// Mock Radix Popover primitives — portals don't work in jsdom
vi.mock('@/components/ui/popover', () => ({
  Popover: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PopoverTrigger: ({
    children,
    asChild,
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => <>{children}</>,
  PopoverContent: ({
    children,
    ...rest
  }: {
    children: React.ReactNode;
    side?: string;
    sideOffset?: number;
    className?: string;
  }) => <div data-testid="popover-content">{children}</div>,
}));

describe('GradeChip', () => {
  describe('renders the correct grade letter', () => {
    it('renders A grade', () => {
      render(<GradeChip grade="A" />);
      expect(screen.getByText(/^A/)).toBeInTheDocument();
    });

    it('renders B grade', () => {
      render(<GradeChip grade="B" />);
      expect(screen.getByText(/^B/)).toBeInTheDocument();
    });

    it('renders C grade', () => {
      render(<GradeChip grade="C" />);
      expect(screen.getByText(/^C/)).toBeInTheDocument();
    });

    it('renders D grade', () => {
      render(<GradeChip grade="D" />);
      expect(screen.getByText(/^D/)).toBeInTheDocument();
    });

    it('renders F grade', () => {
      render(<GradeChip grade="F" />);
      expect(screen.getByText(/^F/)).toBeInTheDocument();
    });
  });

  describe('normalizes lowercase input', () => {
    it('renders lowercase "a" as uppercase A', () => {
      render(<GradeChip grade="a" />);
      expect(screen.getByText(/^A/)).toBeInTheDocument();
    });

    it('renders lowercase "f" as uppercase F', () => {
      render(<GradeChip grade="f" />);
      expect(screen.getByText(/^F/)).toBeInTheDocument();
    });
  });

  describe('colorblind-safe grade indicators', () => {
    it('renders a checkmark suffix for A grade', () => {
      const { container } = render(<GradeChip grade="A" />);
      // The suffix span contains the unicode checkmark \u2713
      const suffixSpan = container.querySelector('span.text-\\[0\\.6rem\\]');
      expect(suffixSpan).toBeInTheDocument();
      expect(suffixSpan?.textContent).toContain('\u2713');
    });

    it('renders a down-arrow suffix for F grade', () => {
      const { container } = render(<GradeChip grade="F" />);
      const suffixSpan = container.querySelector('span.text-\\[0\\.6rem\\]');
      expect(suffixSpan).toBeInTheDocument();
      expect(suffixSpan?.textContent).toContain('\u25BC');
    });

    it('renders a plus suffix for B grade', () => {
      const { container } = render(<GradeChip grade="B" />);
      const suffixSpan = container.querySelector('span.text-\\[0\\.6rem\\]');
      expect(suffixSpan).toBeInTheDocument();
      expect(suffixSpan?.textContent).toContain('+');
    });

    it('renders a tilde suffix for C grade', () => {
      const { container } = render(<GradeChip grade="C" />);
      const suffixSpan = container.querySelector('span.text-\\[0\\.6rem\\]');
      expect(suffixSpan).toBeInTheDocument();
      expect(suffixSpan?.textContent).toContain('~');
    });

    it('renders an exclamation suffix for D grade', () => {
      const { container } = render(<GradeChip grade="D" />);
      const suffixSpan = container.querySelector('span.text-\\[0\\.6rem\\]');
      expect(suffixSpan).toBeInTheDocument();
      expect(suffixSpan?.textContent).toContain('!');
    });
  });

  describe('applies color classes', () => {
    it('applies A color class to the chip', () => {
      const { container } = render(<GradeChip grade="A" />);
      const chip = container.firstChild as HTMLElement;
      expect(chip.className).toContain('bg-[var(--grade-a)]');
    });

    it('applies F color class to the chip', () => {
      const { container } = render(<GradeChip grade="F" />);
      const chip = container.firstChild as HTMLElement;
      expect(chip.className).toContain('bg-[var(--grade-f)]');
    });

    it('falls back to C color for an unknown grade string', () => {
      const { container } = render(<GradeChip grade="Z" />);
      const chip = container.firstChild as HTMLElement;
      expect(chip.className).toContain('bg-[var(--grade-c)]');
    });
  });

  describe('extra className prop', () => {
    it('merges custom className onto the chip', () => {
      const { container } = render(<GradeChip grade="B" className="my-custom-class" />);
      const chip = container.firstChild as HTMLElement;
      expect(chip.className).toContain('my-custom-class');
    });
  });

  describe('reason tooltip', () => {
    it('does not render a tooltip button when no reason is provided', () => {
      render(<GradeChip grade="A" />);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('renders a tooltip button when reason is provided', () => {
      render(<GradeChip grade="B" reason="Good trail braking" />);
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button.className).toContain('cursor-help');
    });

    it('renders the reason text in the popover content', () => {
      render(<GradeChip grade="C" reason="Needs more throttle commitment" />);
      expect(screen.getByText('Needs more throttle commitment')).toBeInTheDocument();
    });

    it('resolves {{speed:N}} markers using the current unit setting', () => {
      render(<GradeChip grade="C" reason="Min speed varies {{speed:5.6}} (31.1-36.5 mph); early apex laps arrive slower." />);
      const content = screen.getByTestId('popover-content');
      expect(content.textContent).toContain('5.6 mph');
      expect(content.textContent).not.toContain('{{speed:');
    });

    it('still displays the grade letter when reason is present', () => {
      render(<GradeChip grade="D" reason="Braking too early" />);
      expect(screen.getByText(/^D/)).toBeInTheDocument();
    });

    it('button click calls stopPropagation', () => {
      render(<GradeChip grade="F" reason="Late apex" />);
      const button = screen.getByRole('button');
      const event = new MouseEvent('click', { bubbles: true, cancelable: true });
      const stopSpy = vi.spyOn(event, 'stopPropagation');
      button.dispatchEvent(event);
      expect(stopSpy).toHaveBeenCalled();
    });
  });
});
