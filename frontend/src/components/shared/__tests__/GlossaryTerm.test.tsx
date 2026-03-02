import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GlossaryTerm } from '../GlossaryTerm';

// Mock useSkillLevel so we can control the skill level in each test
const mockUseSkillLevel = vi.fn();

vi.mock('@/hooks/useSkillLevel', () => ({
  useSkillLevel: () => mockUseSkillLevel(),
}));

// Tooltip primitives from shadcn/ui use Radix under the hood which needs a real
// DOM — stub them out with lightweight wrappers that still render children and
// the tooltip content inline so we can assert on it.
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
  }) => <span data-testid="tooltip-trigger" {...rest}>{children}</span>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="tooltip-content">{children}</div>
  ),
}));

// Use a real glossary entry ('Apex') so we don't have to duplicate the data
const KNOWN_TERM = 'Apex';
const UNKNOWN_TERM = 'Nonexistent Term';

function intermediateSkill() {
  mockUseSkillLevel.mockReturnValue({
    isNovice: false,
    isAdvanced: false,
    skillLevel: 'intermediate',
  });
}

function noviceSkill() {
  mockUseSkillLevel.mockReturnValue({
    isNovice: true,
    isAdvanced: false,
    skillLevel: 'novice',
  });
}

function advancedSkill() {
  mockUseSkillLevel.mockReturnValue({
    isNovice: false,
    isAdvanced: true,
    skillLevel: 'advanced',
  });
}

describe('GlossaryTerm', () => {
  beforeEach(() => {
    intermediateSkill();
  });

  describe('unknown term (no glossary entry)', () => {
    it('renders children as-is when the term is not in the glossary', () => {
      render(
        <GlossaryTerm term={UNKNOWN_TERM}>
          <span>some text</span>
        </GlossaryTerm>,
      );
      expect(screen.getByText('some text')).toBeInTheDocument();
    });

    it('does not render a tooltip trigger for unknown terms', () => {
      render(
        <GlossaryTerm term={UNKNOWN_TERM}>
          <span>some text</span>
        </GlossaryTerm>,
      );
      expect(screen.queryByTestId('tooltip-trigger')).not.toBeInTheDocument();
    });
  });

  describe('advanced skill level', () => {
    it('renders children without a tooltip for advanced users', () => {
      advancedSkill();
      render(
        <GlossaryTerm term={KNOWN_TERM}>
          <span>Apex</span>
        </GlossaryTerm>,
      );
      expect(screen.getByText('Apex')).toBeInTheDocument();
      expect(screen.queryByTestId('tooltip-trigger')).not.toBeInTheDocument();
    });
  });

  describe('intermediate skill level', () => {
    it('renders children inside a tooltip trigger', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>
          <span>Apex</span>
        </GlossaryTerm>,
      );
      expect(screen.getByTestId('tooltip-trigger')).toBeInTheDocument();
      expect(screen.getByText('Apex')).toBeInTheDocument();
    });

    it('renders the technical definition in the tooltip content', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>
          <span>Apex</span>
        </GlossaryTerm>,
      );
      // tooltip-content is always rendered in our stub
      expect(screen.getByTestId('tooltip-content')).toBeInTheDocument();
      // For intermediate, definition (not noviceExplanation) is shown
      expect(
        screen.getByText(/innermost point of your line/i),
      ).toBeInTheDocument();
    });

    it('does not render the example text for intermediate users', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>
          <span>Apex</span>
        </GlossaryTerm>,
      );
      expect(screen.queryByText(/Example:/i)).not.toBeInTheDocument();
    });

    it('applies a muted dotted border to the trigger span', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>Apex</GlossaryTerm>,
      );
      const trigger = screen.getByTestId('tooltip-trigger');
      // The inner span rendered by TooltipTrigger asChild should carry the class
      const innerSpan = trigger.querySelector('span') ?? trigger;
      expect(innerSpan.className).toContain('border-dotted');
    });
  });

  describe('novice skill level', () => {
    beforeEach(() => {
      noviceSkill();
    });

    it('renders the novice explanation in the tooltip content', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>
          <span>Apex</span>
        </GlossaryTerm>,
      );
      expect(
        screen.getByText(/closest point to the inside of a turn/i),
      ).toBeInTheDocument();
    });

    it('renders the example text for novice users when entry has an example', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>
          <span>Apex</span>
        </GlossaryTerm>,
      );
      expect(screen.getByText(/Example:/i)).toBeInTheDocument();
    });

    it('applies an accent dotted border for novice users', () => {
      render(
        <GlossaryTerm term={KNOWN_TERM}>Apex</GlossaryTerm>,
      );
      const trigger = screen.getByTestId('tooltip-trigger');
      const innerSpan = trigger.querySelector('span') ?? trigger;
      expect(innerSpan.className).toContain('border-[var(--cata-accent)]');
    });
  });
});
