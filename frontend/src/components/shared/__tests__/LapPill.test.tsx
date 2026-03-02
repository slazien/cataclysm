import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LapPill } from '../LapPill';

// motion/react — replace with a plain <button> that strips Framer Motion-only
// props (whileTap, whileHover, transition) so React doesn't warn about unknown
// DOM attributes.
vi.mock('motion/react', () => ({
  motion: {
    button: ({
      children,
      className,
      onClick,
      type,
      style,
      // Strip Framer Motion props that are not valid HTML attributes
      whileTap: _whileTap,
      whileHover: _whileHover,
      transition: _transition,
      variants: _variants,
      initial: _initial,
      animate: _animate,
      ...rest
    }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
      style?: React.CSSProperties;
      whileTap?: unknown;
      whileHover?: unknown;
      transition?: unknown;
      variants?: unknown;
      initial?: unknown;
      animate?: unknown;
    }) => (
      <button type={type} className={className} onClick={onClick} style={style} {...rest}>
        {children}
      </button>
    ),
  },
}));

vi.mock('@/lib/design-tokens', () => ({
  motion: { pillPress: {} },
  colors: {
    lap: ['#58a6ff', '#f97316', '#22c55e', '#e879f9'],
    comparison: { reference: '#58a6ff', compare: '#f97316' },
  },
}));

describe('LapPill', () => {
  describe('basic rendering', () => {
    it('renders the lap number prefixed with L', () => {
      render(<LapPill lapNumber={7} time="1:23.456" />);
      expect(screen.getByText('L7')).toBeInTheDocument();
    });

    it('renders the lap time', () => {
      render(<LapPill lapNumber={3} time="1:24.100" />);
      expect(screen.getByText('1:24.100')).toBeInTheDocument();
    });

    it('renders a button element', () => {
      render(<LapPill lapNumber={1} time="1:20.000" />);
      expect(screen.getByRole('button')).toBeInTheDocument();
    });
  });

  describe('PB indicator', () => {
    it('renders a star aria-label when isPb is true', () => {
      render(<LapPill lapNumber={5} time="1:22.000" isPb />);
      expect(screen.getByLabelText('Personal best')).toBeInTheDocument();
    });

    it('does not render the star label when isPb is false', () => {
      render(<LapPill lapNumber={5} time="1:22.000" isPb={false} />);
      expect(screen.queryByLabelText('Personal best')).not.toBeInTheDocument();
    });

    it('does not render the star label when isPb is omitted', () => {
      render(<LapPill lapNumber={5} time="1:22.000" />);
      expect(screen.queryByLabelText('Personal best')).not.toBeInTheDocument();
    });
  });

  describe('selected state', () => {
    it('renders border-transparent class when selected', () => {
      const { container } = render(<LapPill lapNumber={1} time="1:20.000" selected />);
      const btn = container.querySelector('button')!;
      expect(btn.className).toContain('border-transparent');
    });

    it('renders border-[var(--cata-border)] class when not selected', () => {
      const { container } = render(<LapPill lapNumber={1} time="1:20.000" selected={false} />);
      const btn = container.querySelector('button')!;
      expect(btn.className).toContain('border-[var(--cata-border)]');
    });

    it('applies inline background color style when selected', () => {
      const { container } = render(<LapPill lapNumber={1} time="1:20.000" selected colorIndex={0} />);
      const btn = container.querySelector('button')!;
      expect(btn.style.backgroundColor).toBeTruthy();
    });

    it('does not apply inline background color style when not selected', () => {
      const { container } = render(<LapPill lapNumber={1} time="1:20.000" selected={false} />);
      const btn = container.querySelector('button')!;
      expect(btn.style.backgroundColor).toBeFalsy();
    });
  });

  describe('role labels (reference / compare)', () => {
    it('renders REF label when selected and role is reference', () => {
      render(<LapPill lapNumber={1} time="1:20.000" selected role="reference" />);
      expect(screen.getByText('REF')).toBeInTheDocument();
    });

    it('renders CMP label when selected and role is compare', () => {
      render(<LapPill lapNumber={2} time="1:21.000" selected role="compare" />);
      expect(screen.getByText('CMP')).toBeInTheDocument();
    });

    it('does not render role labels when not selected', () => {
      render(<LapPill lapNumber={1} time="1:20.000" selected={false} role="reference" />);
      expect(screen.queryByText('REF')).not.toBeInTheDocument();
    });

    it('does not render role labels when role is not provided', () => {
      render(<LapPill lapNumber={1} time="1:20.000" selected />);
      expect(screen.queryByText('REF')).not.toBeInTheDocument();
      expect(screen.queryByText('CMP')).not.toBeInTheDocument();
    });
  });

  describe('click handler', () => {
    it('calls onClick when the pill is clicked', () => {
      const onClick = vi.fn();
      render(<LapPill lapNumber={3} time="1:23.000" onClick={onClick} />);
      fireEvent.click(screen.getByRole('button'));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('does not throw when onClick is not provided and the pill is clicked', () => {
      render(<LapPill lapNumber={3} time="1:23.000" />);
      expect(() => fireEvent.click(screen.getByRole('button'))).not.toThrow();
    });
  });

  describe('colorIndex prop', () => {
    it('wraps colorIndex around the colors.lap array length', () => {
      // colorIndex=0 → colors.lap[0], colorIndex=4 → colors.lap[4 % 4] = colors.lap[0]
      // Both should have the same backgroundColor when selected
      const { container: c1 } = render(
        <LapPill lapNumber={1} time="1:20.000" selected colorIndex={0} />,
      );
      const { container: c2 } = render(
        <LapPill lapNumber={1} time="1:20.000" selected colorIndex={4} />,
      );
      const btn1 = c1.querySelector('button')!;
      const btn2 = c2.querySelector('button')!;
      expect(btn1.style.backgroundColor).toBe(btn2.style.backgroundColor);
    });
  });

  describe('extra className', () => {
    it('merges a custom className onto the button', () => {
      const { container } = render(<LapPill lapNumber={1} time="1:20.000" className="mt-2" />);
      expect(container.querySelector('button')!.className).toContain('mt-2');
    });
  });
});
