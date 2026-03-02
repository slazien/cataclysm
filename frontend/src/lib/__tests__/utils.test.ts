import { cn } from '../utils';

// cn() is a thin wrapper around clsx + tailwind-merge.
// It merges class names, resolves Tailwind conflicts, and filters falsy values.

describe('cn', () => {
  // -------------------------------------------------------------------------
  // Basic string merging
  // -------------------------------------------------------------------------
  describe('basic class merging', () => {
    it('returns a single class name unchanged', () => {
      expect(cn('foo')).toBe('foo');
    });

    it('joins multiple class strings with spaces', () => {
      expect(cn('foo', 'bar')).toBe('foo bar');
    });

    it('joins three class strings', () => {
      expect(cn('a', 'b', 'c')).toBe('a b c');
    });

    it('returns empty string when called with no arguments', () => {
      expect(cn()).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // Falsy value filtering (clsx behaviour)
  // -------------------------------------------------------------------------
  describe('falsy value filtering', () => {
    it('ignores false values', () => {
      expect(cn('foo', false, 'bar')).toBe('foo bar');
    });

    it('ignores undefined values', () => {
      expect(cn('foo', undefined, 'bar')).toBe('foo bar');
    });

    it('ignores null values', () => {
      expect(cn('foo', null, 'bar')).toBe('foo bar');
    });

    it('ignores empty strings', () => {
      expect(cn('foo', '', 'bar')).toBe('foo bar');
    });

    it('returns empty string when all values are falsy', () => {
      expect(cn(false, undefined, null)).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // Conditional class object syntax (clsx behaviour)
  // -------------------------------------------------------------------------
  describe('conditional object syntax', () => {
    it('includes class when condition is true', () => {
      expect(cn({ active: true })).toBe('active');
    });

    it('excludes class when condition is false', () => {
      expect(cn({ active: false })).toBe('');
    });

    it('includes only truthy keys from an object', () => {
      expect(cn({ a: true, b: false, c: true })).toBe('a c');
    });

    it('mixes strings and conditional objects', () => {
      expect(cn('base', { active: true, disabled: false })).toBe('base active');
    });
  });

  // -------------------------------------------------------------------------
  // Array inputs (clsx behaviour)
  // -------------------------------------------------------------------------
  describe('array inputs', () => {
    it('accepts an array of class strings', () => {
      expect(cn(['foo', 'bar'])).toBe('foo bar');
    });

    it('accepts nested arrays', () => {
      expect(cn(['foo', ['bar', 'baz']])).toBe('foo bar baz');
    });

    it('filters falsy values within arrays', () => {
      expect(cn(['foo', false, 'bar'])).toBe('foo bar');
    });
  });

  // -------------------------------------------------------------------------
  // Tailwind conflict resolution (tailwind-merge behaviour)
  // -------------------------------------------------------------------------
  describe('Tailwind conflict resolution', () => {
    it('last padding class wins when there is a conflict', () => {
      // tailwind-merge removes 'p-4' in favour of 'p-8'
      expect(cn('p-4', 'p-8')).toBe('p-8');
    });

    it('last text-colour class wins', () => {
      expect(cn('text-red-500', 'text-blue-600')).toBe('text-blue-600');
    });

    it('merges non-conflicting Tailwind classes normally', () => {
      expect(cn('p-4', 'mt-2')).toBe('p-4 mt-2');
    });

    it('deduplicates identical class names', () => {
      expect(cn('flex', 'flex')).toBe('flex');
    });

    it('handles conditional Tailwind classes with conflict resolution', () => {
      const isActive = true;
      expect(cn('bg-gray-100', { 'bg-blue-500': isActive })).toBe('bg-blue-500');
    });
  });

  // -------------------------------------------------------------------------
  // Edge cases
  // -------------------------------------------------------------------------
  describe('edge cases', () => {
    it('handles a class with extra whitespace (trimmed by clsx)', () => {
      // clsx trims internal spaces; result should not have doubled spaces
      const result = cn('  foo  ');
      expect(result.trim()).toBe('foo');
    });

    it('handles very long list of classes', () => {
      const classes = Array.from({ length: 20 }, (_, i) => `class-${i}`);
      const result = cn(...classes);
      expect(result).toContain('class-0');
      expect(result).toContain('class-19');
    });
  });
});
