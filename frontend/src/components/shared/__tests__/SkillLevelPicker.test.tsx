import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SkillLevelPicker, shouldShowSkillPicker } from '../SkillLevelPicker';

// Mock motion/react to avoid animation timing issues in tests
vi.mock('motion/react', () => ({
  motion: {
    div: ({
      children,
      ...props
    }: React.PropsWithChildren<React.HTMLAttributes<HTMLDivElement>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

// Mock the api module
vi.mock('@/lib/api', () => ({
  updateUserProfile: vi.fn().mockResolvedValue({}),
}));

// Mock the store
const mockSetSkillLevel = vi.fn();
vi.mock('@/stores', () => ({
  useUiStore: (selector: (state: { setSkillLevel: typeof mockSetSkillLevel }) => unknown) =>
    selector({ setSkillLevel: mockSetSkillLevel }),
}));

describe('shouldShowSkillPicker', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('returns true when localStorage flag is not set', () => {
    expect(shouldShowSkillPicker()).toBe(true);
  });

  it('returns false when localStorage flag is set', () => {
    localStorage.setItem('cataclysm-skill-level-set', '1');
    expect(shouldShowSkillPicker()).toBe(false);
  });
});

describe('SkillLevelPicker', () => {
  beforeEach(() => {
    localStorage.clear();
    mockSetSkillLevel.mockClear();
  });

  it('renders the heading and subtitle', () => {
    render(<SkillLevelPicker onComplete={vi.fn()} />);
    expect(
      screen.getByText('How many trackdays have you done?'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        'This adjusts your coaching and which features we show you.',
      ),
    ).toBeInTheDocument();
  });

  it('renders three skill level buttons', () => {
    render(<SkillLevelPicker onComplete={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Less than 5' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /5\s*\u2013\s*20/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'More than 20' })).toBeInTheDocument();
  });

  it('has an accessible dialog role', () => {
    render(<SkillLevelPicker onComplete={vi.fn()} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('calls setSkillLevel with novice and onComplete when "Less than 5" is clicked', async () => {
    const onComplete = vi.fn();
    render(<SkillLevelPicker onComplete={onComplete} />);

    fireEvent.click(screen.getByRole('button', { name: 'Less than 5' }));

    expect(mockSetSkillLevel).toHaveBeenCalledWith('novice');
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('cataclysm-skill-level-set')).toBe('1');
  });

  it('calls setSkillLevel with intermediate when "5 – 20" is clicked', () => {
    const onComplete = vi.fn();
    render(<SkillLevelPicker onComplete={onComplete} />);

    fireEvent.click(screen.getByRole('button', { name: /5\s*\u2013\s*20/ }));

    expect(mockSetSkillLevel).toHaveBeenCalledWith('intermediate');
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('calls setSkillLevel with advanced when "More than 20" is clicked', () => {
    const onComplete = vi.fn();
    render(<SkillLevelPicker onComplete={onComplete} />);

    fireEvent.click(screen.getByRole('button', { name: 'More than 20' }));

    expect(mockSetSkillLevel).toHaveBeenCalledWith('advanced');
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it('calls updateUserProfile fire-and-forget on selection', async () => {
    const { updateUserProfile } = await import('@/lib/api');
    const onComplete = vi.fn();
    render(<SkillLevelPicker onComplete={onComplete} />);

    fireEvent.click(screen.getByRole('button', { name: 'Less than 5' }));

    expect(updateUserProfile).toHaveBeenCalledWith({ skill_level: 'novice' });
  });

  it('buttons have minimum touch target height of 56px', () => {
    render(<SkillLevelPicker onComplete={vi.fn()} />);
    const buttons = screen.getAllByRole('button');
    buttons.forEach((btn) => {
      expect(btn.className).toContain('min-h-[56px]');
    });
  });
});
