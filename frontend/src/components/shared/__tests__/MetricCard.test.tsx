import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { MetricCard } from '../MetricCard';

vi.mock('motion/react', () => ({
  motion: {
    div: ({ children, className, ...rest }: React.HTMLAttributes<HTMLDivElement>) => (
      <div className={className} {...rest}>
        {children}
      </div>
    ),
  },
}));

vi.mock('@/lib/design-tokens', () => ({
  motion: { cardEntrance: {} },
  colors: {
    lap: ['#58a6ff'],
    comparison: { reference: '#58a6ff', compare: '#f97316' },
  },
}));

describe('MetricCard', () => {
  describe('renders label and value', () => {
    it('renders the label text', () => {
      render(<MetricCard label="Lap Time" value="1:23.456" />);
      expect(screen.getByText('Lap Time')).toBeInTheDocument();
    });

    it('renders a string value', () => {
      render(<MetricCard label="Top Speed" value="142.5 mph" />);
      expect(screen.getByText('142.5 mph')).toBeInTheDocument();
    });

    it('renders a numeric value', () => {
      render(<MetricCard label="Laps" value={12} />);
      expect(screen.getByText('12')).toBeInTheDocument();
    });

    it('renders zero as a value', () => {
      render(<MetricCard label="Errors" value={0} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });
  });

  describe('delta display', () => {
    it('does not render a delta row when delta is omitted', () => {
      const { container } = render(<MetricCard label="Top Speed" value="142 mph" />);
      // The delta/subtitle wrapper div should be absent
      expect(container.querySelector('.mt-0\\.5.flex')).not.toBeInTheDocument();
    });

    it('renders a positive delta with a + sign', () => {
      render(<MetricCard label="Gap" value="–" delta={0.312} />);
      expect(screen.getByText('+0.312s')).toBeInTheDocument();
    });

    it('renders a negative delta without a + sign', () => {
      render(<MetricCard label="Gap" value="–" delta={-0.125} />);
      expect(screen.getByText('-0.125s')).toBeInTheDocument();
    });

    it('renders zero delta with three decimal places and no + sign', () => {
      render(<MetricCard label="Gap" value="–" delta={0} />);
      expect(screen.getByText('0.000s')).toBeInTheDocument();
    });

    it('renders deltaLabel next to delta value', () => {
      render(<MetricCard label="Gap" value="–" delta={-0.2} deltaLabel="vs PB" />);
      expect(screen.getByText('vs PB')).toBeInTheDocument();
    });

    it('renders subtitle when no delta is provided', () => {
      render(<MetricCard label="Track" value="Barber" subtitle="Alabama, USA" />);
      expect(screen.getByText('Alabama, USA')).toBeInTheDocument();
    });

    it('prefers deltaLabel over subtitle when both are supplied', () => {
      render(
        <MetricCard
          label="Gap"
          value="–"
          delta={-0.1}
          deltaLabel="vs P1"
          subtitle="fallback"
        />,
      );
      expect(screen.getByText('vs P1')).toBeInTheDocument();
      expect(screen.queryByText('fallback')).not.toBeInTheDocument();
    });
  });

  describe('highlight styling', () => {
    it('applies pb highlight class', () => {
      const { container } = render(<MetricCard label="L" value="v" highlight="pb" />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-[var(--color-pb)]');
    });

    it('applies good highlight class', () => {
      const { container } = render(<MetricCard label="L" value="v" highlight="good" />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-[var(--color-throttle)]');
    });

    it('applies bad highlight class', () => {
      const { container } = render(<MetricCard label="L" value="v" highlight="bad" />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-[var(--color-brake)]');
    });

    it('applies none highlight class by default', () => {
      const { container } = render(<MetricCard label="L" value="v" />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('border-[var(--cata-border)]');
    });
  });

  describe('extra className prop', () => {
    it('merges custom className', () => {
      const { container } = render(<MetricCard label="L" value="v" className="w-full" />);
      const card = container.firstChild as HTMLElement;
      expect(card.className).toContain('w-full');
    });
  });
});
