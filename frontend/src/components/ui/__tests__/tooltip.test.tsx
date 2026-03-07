import '@testing-library/jest-dom/vitest';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '../tooltip';

// Radix UI Portal needs a real DOM parent — mock the Portal to render inline
vi.mock('radix-ui', () => {
  const TooltipPrimitive = {
    Provider: ({ children, ...props }: { children: React.ReactNode; delayDuration?: number }) => (
      <div data-testid="tooltip-provider" {...props}>
        {children}
      </div>
    ),
    Root: ({ children, ...props }: { children: React.ReactNode }) => (
      <div data-testid="tooltip-root" {...props}>
        {children}
      </div>
    ),
    Trigger: ({
      children,
      ...props
    }: {
      children: React.ReactNode;
      asChild?: boolean;
    }) => (
      <div data-testid="tooltip-trigger" {...props}>
        {children}
      </div>
    ),
    Content: ({
      children,
      className,
      sideOffset,
      ...props
    }: {
      children: React.ReactNode;
      className?: string;
      sideOffset?: number;
    }) => (
      <div data-testid="tooltip-content" className={className} {...props}>
        {children}
      </div>
    ),
    Portal: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    Arrow: ({ className }: { className?: string }) => (
      <div data-testid="tooltip-arrow" className={className} />
    ),
  };
  return { Tooltip: TooltipPrimitive };
});

describe('TooltipProvider', () => {
  it('renders children', () => {
    render(
      <TooltipProvider>
        <span>provider child</span>
      </TooltipProvider>,
    );
    expect(screen.getByText('provider child')).toBeInTheDocument();
  });

  it('sets data-slot="tooltip-provider"', () => {
    render(
      <TooltipProvider>
        <span>child</span>
      </TooltipProvider>,
    );
    const el = screen.getByTestId('tooltip-provider');
    expect(el).toHaveAttribute('data-slot', 'tooltip-provider');
  });

  it('defaults delayDuration to 0', () => {
    render(
      <TooltipProvider>
        <span>child</span>
      </TooltipProvider>,
    );
    const el = screen.getByTestId('tooltip-provider');
    expect(el).toHaveAttribute('delayDuration', '0');
  });

  it('accepts custom delayDuration', () => {
    render(
      <TooltipProvider delayDuration={300}>
        <span>child</span>
      </TooltipProvider>,
    );
    const el = screen.getByTestId('tooltip-provider');
    expect(el).toHaveAttribute('delayDuration', '300');
  });
});

describe('Tooltip', () => {
  it('renders children', () => {
    render(
      <Tooltip>
        <span>tooltip child</span>
      </Tooltip>,
    );
    expect(screen.getByText('tooltip child')).toBeInTheDocument();
  });

  it('sets data-slot="tooltip"', () => {
    render(
      <Tooltip>
        <span>child</span>
      </Tooltip>,
    );
    const el = screen.getByTestId('tooltip-root');
    expect(el).toHaveAttribute('data-slot', 'tooltip');
  });
});

describe('TooltipTrigger', () => {
  it('renders children', () => {
    render(
      <TooltipTrigger>
        <button>trigger</button>
      </TooltipTrigger>,
    );
    expect(screen.getByText('trigger')).toBeInTheDocument();
  });

  it('sets data-slot="tooltip-trigger"', () => {
    render(
      <TooltipTrigger>
        <button>trigger</button>
      </TooltipTrigger>,
    );
    const el = screen.getByTestId('tooltip-trigger');
    expect(el).toHaveAttribute('data-slot', 'tooltip-trigger');
  });
});

describe('TooltipContent', () => {
  it('renders children content', () => {
    render(<TooltipContent>Tooltip text</TooltipContent>);
    expect(screen.getByText('Tooltip text')).toBeInTheDocument();
  });

  it('sets data-slot="tooltip-content"', () => {
    render(<TooltipContent>text</TooltipContent>);
    const el = screen.getByTestId('tooltip-content');
    expect(el).toHaveAttribute('data-slot', 'tooltip-content');
  });

  it('renders the arrow element', () => {
    render(<TooltipContent>text</TooltipContent>);
    const arrow = screen.getByTestId('tooltip-arrow');
    expect(arrow).toBeInTheDocument();
  });

  it('merges custom className with default classes', () => {
    render(<TooltipContent className="custom-class">text</TooltipContent>);
    const el = screen.getByTestId('tooltip-content');
    expect(el.className).toContain('custom-class');
  });
});

describe('Full tooltip composition', () => {
  it('renders a complete tooltip structure', () => {
    render(
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger>
            <button>Hover me</button>
          </TooltipTrigger>
          <TooltipContent>Helpful info</TooltipContent>
        </Tooltip>
      </TooltipProvider>,
    );
    expect(screen.getByText('Hover me')).toBeInTheDocument();
    expect(screen.getByText('Helpful info')).toBeInTheDocument();
  });
});
