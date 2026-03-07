import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { Button, buttonVariants } from '../button';

// Mock radix-ui Slot to forward props to children
vi.mock('radix-ui', () => ({
  Slot: {
    Root: ({
      children,
      ...props
    }: {
      children: React.ReactElement;
      [key: string]: unknown;
    }) => {
      // Slot renders its child with merged props
      if (children && typeof children === 'object') {
        return <span data-testid="slot-root" {...props}>{children}</span>;
      }
      return children;
    },
  },
}));

describe('Button', () => {
  it('renders a button element by default', () => {
    render(<Button>Click me</Button>);
    const button = screen.getByRole('button', { name: 'Click me' });
    expect(button).toBeInTheDocument();
    expect(button.tagName).toBe('BUTTON');
  });

  it('sets data-slot="button"', () => {
    render(<Button>Click</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('data-slot', 'button');
  });

  it('sets data-variant to the variant prop', () => {
    render(<Button variant="destructive">Delete</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('data-variant', 'destructive');
  });

  it('sets data-size to the size prop', () => {
    render(<Button size="lg">Large</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('data-size', 'lg');
  });

  it('defaults to variant="default" and size="default"', () => {
    render(<Button>Default</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('data-variant', 'default');
    expect(button).toHaveAttribute('data-size', 'default');
  });

  it('applies custom className', () => {
    render(<Button className="custom-btn">Styled</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('custom-btn');
  });

  it('passes through onClick handler', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Clickable</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is passed', () => {
    render(<Button disabled>Disabled</Button>);
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });

  it('passes type attribute', () => {
    render(<Button type="submit">Submit</Button>);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('type', 'submit');
  });

  describe('variant styles', () => {
    it('applies default variant classes', () => {
      render(<Button variant="default">Default</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('bg-primary');
    });

    it('applies destructive variant classes', () => {
      render(<Button variant="destructive">Delete</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('bg-destructive');
    });

    it('applies outline variant classes', () => {
      render(<Button variant="outline">Outline</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('border');
    });

    it('applies secondary variant classes', () => {
      render(<Button variant="secondary">Secondary</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('bg-secondary');
    });

    it('applies ghost variant classes', () => {
      render(<Button variant="ghost">Ghost</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('hover:bg-accent');
    });

    it('applies link variant classes', () => {
      render(<Button variant="link">Link</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('underline-offset-4');
    });
  });

  describe('size styles', () => {
    it('applies xs size', () => {
      render(<Button size="xs">XS</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('h-6');
    });

    it('applies sm size', () => {
      render(<Button size="sm">SM</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('h-8');
    });

    it('applies lg size', () => {
      render(<Button size="lg">LG</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('h-10');
    });

    it('applies icon size', () => {
      render(<Button size="icon">I</Button>);
      const button = screen.getByRole('button');
      expect(button.className).toContain('size-9');
    });
  });

  describe('asChild', () => {
    it('renders Slot.Root when asChild is true', () => {
      render(
        <Button asChild>
          <a href="/test">Link Button</a>
        </Button>,
      );
      const slotRoot = screen.getByTestId('slot-root');
      expect(slotRoot).toBeInTheDocument();
      expect(slotRoot).toHaveAttribute('data-slot', 'button');
    });
  });
});

describe('buttonVariants', () => {
  it('returns a string of class names', () => {
    const result = buttonVariants({ variant: 'default', size: 'default' });
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('includes variant-specific classes', () => {
    const result = buttonVariants({ variant: 'destructive' });
    expect(result).toContain('bg-destructive');
  });

  it('includes size-specific classes', () => {
    const result = buttonVariants({ size: 'lg' });
    expect(result).toContain('h-10');
  });
});
