import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SignUpCTA } from '../SignUpCTA';

vi.mock('lucide-react', () => ({
  X: ({ className }: { className?: string }) => (
    <svg data-testid="x-icon" className={className} />
  ),
}));

describe('SignUpCTA', () => {
  it('renders the CTA banner on initial render', () => {
    render(<SignUpCTA />);
    expect(screen.getByText('Analyze your own track days')).toBeInTheDocument();
    expect(
      screen.getByText('AI coaching, corner analysis, and progress tracking'),
    ).toBeInTheDocument();
  });

  it('renders a sign-up link pointing to /api/auth/signin', () => {
    render(<SignUpCTA />);
    const link = screen.getByRole('link', { name: /sign up free/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/api/auth/signin');
  });

  it('renders a dismiss button with accessible label', () => {
    render(<SignUpCTA />);
    const dismissButton = screen.getByRole('button', { name: /dismiss/i });
    expect(dismissButton).toBeInTheDocument();
  });

  it('hides the banner when the dismiss button is clicked', () => {
    render(<SignUpCTA />);
    expect(screen.getByText('Analyze your own track days')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }));

    expect(screen.queryByText('Analyze your own track days')).not.toBeInTheDocument();
  });

  it('renders the X icon inside the dismiss button', () => {
    render(<SignUpCTA />);
    expect(screen.getByTestId('x-icon')).toBeInTheDocument();
  });
});
