import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EmptyState } from '../EmptyState';
import type { LucideIcon } from 'lucide-react';

// Minimal stub LucideIcon — a functional React component with the right signature
const TestIcon: LucideIcon = ({ className }: { className?: string }) => (
  <svg data-testid="custom-icon" className={className} />
);
// LucideIcon has static properties that aren't called during rendering; cast satisfies TS
const StubIcon = TestIcon as unknown as LucideIcon;

describe('EmptyState', () => {
  describe('default rendering', () => {
    it('renders the default title when no title prop is supplied', () => {
      render(<EmptyState />);
      expect(screen.getByText('No session loaded')).toBeInTheDocument();
    });

    it('renders the default message when no message prop is supplied', () => {
      render(<EmptyState />);
      expect(screen.getByText('Upload a RaceChrono CSV to get started')).toBeInTheDocument();
    });

    it('renders the fallback SVG upload icon when no icon prop is supplied', () => {
      const { container } = render(<EmptyState />);
      // The fallback is an <svg> without a data-testid
      const svgs = container.querySelectorAll('svg');
      expect(svgs.length).toBe(1);
      expect(screen.queryByTestId('custom-icon')).not.toBeInTheDocument();
    });
  });

  describe('custom title and message', () => {
    it('renders a custom title', () => {
      render(<EmptyState title="Nothing here yet" />);
      expect(screen.getByText('Nothing here yet')).toBeInTheDocument();
    });

    it('renders a custom message', () => {
      render(<EmptyState message="Select a session from the drawer." />);
      expect(screen.getByText('Select a session from the drawer.')).toBeInTheDocument();
    });
  });

  describe('icon prop', () => {
    it('renders the provided LucideIcon instead of the fallback', () => {
      render(<EmptyState icon={StubIcon} />);
      expect(screen.getByTestId('custom-icon')).toBeInTheDocument();
    });

    it('does not render the fallback SVG when icon prop is provided', () => {
      const { container } = render(<EmptyState icon={StubIcon} />);
      const svgs = container.querySelectorAll('svg');
      // Only the StubIcon svg should be present
      expect(svgs.length).toBe(1);
      expect(svgs[0]).toBe(screen.getByTestId('custom-icon'));
    });
  });

  describe('action button', () => {
    it('renders the action button with correct label', () => {
      render(<EmptyState action={{ label: 'Upload CSV', onClick: vi.fn() }} />);
      expect(screen.getByRole('button', { name: 'Upload CSV' })).toBeInTheDocument();
    });

    it('calls the onClick handler when the action button is clicked', () => {
      const onClick = vi.fn();
      render(<EmptyState action={{ label: 'Upload CSV', onClick }} />);
      fireEvent.click(screen.getByRole('button', { name: 'Upload CSV' }));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it('does not render an action button when action prop is omitted', () => {
      render(<EmptyState />);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('children slot', () => {
    it('renders children inside the component', () => {
      render(
        <EmptyState>
          <span data-testid="child-slot">Extra content</span>
        </EmptyState>,
      );
      expect(screen.getByTestId('child-slot')).toBeInTheDocument();
      expect(screen.getByText('Extra content')).toBeInTheDocument();
    });
  });

  describe('extra className prop', () => {
    it('merges a custom className onto the root element', () => {
      const { container } = render(<EmptyState className="mt-8" />);
      expect((container.firstChild as HTMLElement).className).toContain('mt-8');
    });
  });
});
