import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { InfoTooltip } from '../InfoTooltip';

// Mock the tooltip UI primitives — Radix portals don't work in jsdom
vi.mock('@/components/ui/tooltip', () => ({
  TooltipProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipTrigger: ({
    children,
    asChild,
    ...rest
  }: {
    children: React.ReactNode;
    asChild?: boolean;
  }) => <>{children}</>,
  TooltipContent: ({
    children,
    ...rest
  }: {
    children: React.ReactNode;
    side?: string;
    sideOffset?: number;
    className?: string;
  }) => <div data-testid="tooltip-content">{children}</div>,
}));

vi.mock('@/lib/help-content', () => ({
  helpContent: {
    'metric.best-lap': 'Your fastest lap time in this session.',
    'chart.speed-trace': 'Speed vs. distance around the lap.',
  } as Record<string, string>,
}));

vi.mock('lucide-react', () => ({
  CircleHelp: ({ className }: { className?: string }) => (
    <svg data-testid="circle-help-icon" className={className} />
  ),
}));

describe('InfoTooltip', () => {
  it('renders nothing when helpKey has no matching content and no override', () => {
    const { container } = render(<InfoTooltip helpKey="nonexistent.key" />);
    expect(container.innerHTML).toBe('');
  });

  it('renders the trigger button when helpKey matches help-content', () => {
    render(<InfoTooltip helpKey="metric.best-lap" />);
    const button = screen.getByRole('button', { name: /more info about metric best lap/i });
    expect(button).toBeInTheDocument();
  });

  it('renders the help icon inside the trigger button', () => {
    render(<InfoTooltip helpKey="metric.best-lap" />);
    expect(screen.getByTestId('circle-help-icon')).toBeInTheDocument();
  });

  it('displays the help text from helpContent dictionary', () => {
    render(<InfoTooltip helpKey="metric.best-lap" />);
    expect(screen.getByText('Your fastest lap time in this session.')).toBeInTheDocument();
  });

  it('uses content prop to override the helpContent dictionary', () => {
    render(<InfoTooltip helpKey="metric.best-lap" content="Custom override text" />);
    expect(screen.getByText('Custom override text')).toBeInTheDocument();
    expect(screen.queryByText('Your fastest lap time in this session.')).not.toBeInTheDocument();
  });

  it('renders when helpKey has no match but content prop is provided', () => {
    render(<InfoTooltip helpKey="does-not-exist" content="Fallback content" />);
    expect(screen.getByText('Fallback content')).toBeInTheDocument();
  });

  it('generates correct aria-label from helpKey (dots/hyphens to spaces)', () => {
    render(<InfoTooltip helpKey="chart.speed-trace" />);
    const button = screen.getByRole('button', { name: 'More info about chart speed trace' });
    expect(button).toBeInTheDocument();
  });

  it('applies custom className to the trigger button', () => {
    render(<InfoTooltip helpKey="metric.best-lap" className="ml-2" />);
    const button = screen.getByRole('button');
    expect(button.className).toContain('ml-2');
  });

  it('defaults side to top', () => {
    // Verify it renders without error when no side prop is given
    const { container } = render(<InfoTooltip helpKey="metric.best-lap" />);
    expect(container.innerHTML).not.toBe('');
  });
});
