import '@testing-library/jest-dom/vitest';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SkeletonCard } from '../SkeletonCard';

describe('SkeletonCard', () => {
  it('renders a div element', () => {
    const { container } = render(<SkeletonCard />);
    expect(container.firstChild).toBeInstanceOf(HTMLDivElement);
  });

  it('applies animate-pulse class for the skeleton animation', () => {
    const { container } = render(<SkeletonCard />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('animate-pulse');
  });

  it('applies default height class h-24 when no height prop is given', () => {
    const { container } = render(<SkeletonCard />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('h-24');
  });

  it('applies custom height class when height prop is provided', () => {
    const { container } = render(<SkeletonCard height="h-40" />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('h-40');
    expect(div.className).not.toContain('h-24');
  });

  it('applies custom className when provided', () => {
    const { container } = render(<SkeletonCard className="my-custom" />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('my-custom');
  });

  it('merges height and className together', () => {
    const { container } = render(<SkeletonCard height="h-60" className="w-full" />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('h-60');
    expect(div.className).toContain('w-full');
  });

  it('applies bg-elevated background class', () => {
    const { container } = render(<SkeletonCard />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('bg-[var(--bg-elevated)]');
  });

  it('applies rounded-lg class', () => {
    const { container } = render(<SkeletonCard />);
    const div = container.firstChild as HTMLElement;
    expect(div.className).toContain('rounded-lg');
  });
});
