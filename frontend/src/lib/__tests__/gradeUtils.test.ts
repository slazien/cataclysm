import { worstGrade } from '../gradeUtils';

// GRADE_ORDER inside the module is ['A', 'B', 'C', 'D', 'F']
// worstGrade() returns the highest-index (worst) grade from the array,
// defaulting to 'C' when the input array is empty or contains only unknowns.

describe('worstGrade', () => {
  // -------------------------------------------------------------------------
  // Single grade inputs
  // -------------------------------------------------------------------------
  describe('single grade', () => {
    it('returns "A" when the only grade is A', () => {
      expect(worstGrade(['A'])).toBe('A');
    });

    it('returns "B" when the only grade is B', () => {
      expect(worstGrade(['B'])).toBe('B');
    });

    it('returns "C" when the only grade is C', () => {
      expect(worstGrade(['C'])).toBe('C');
    });

    it('returns "D" when the only grade is D', () => {
      expect(worstGrade(['D'])).toBe('D');
    });

    it('returns "F" when the only grade is F', () => {
      expect(worstGrade(['F'])).toBe('F');
    });
  });

  // -------------------------------------------------------------------------
  // Multiple grades — always returns the worst one
  // -------------------------------------------------------------------------
  describe('multiple grades', () => {
    it('returns the worst grade from a mixed list (F wins)', () => {
      expect(worstGrade(['A', 'B', 'F'])).toBe('F');
    });

    it('returns "D" when D is the worst among A, B, C, D', () => {
      expect(worstGrade(['A', 'B', 'C', 'D'])).toBe('D');
    });

    it('returns "B" when B is the worst among A, A, B, A', () => {
      expect(worstGrade(['A', 'A', 'B', 'A'])).toBe('B');
    });

    it('returns "F" when all grades are F', () => {
      expect(worstGrade(['F', 'F', 'F'])).toBe('F');
    });

    it('returns "A" when all grades are A', () => {
      expect(worstGrade(['A', 'A', 'A'])).toBe('A');
    });

    it('handles a two-element list with A and F', () => {
      expect(worstGrade(['A', 'F'])).toBe('F');
      expect(worstGrade(['F', 'A'])).toBe('F');
    });
  });

  // -------------------------------------------------------------------------
  // Case insensitivity
  // -------------------------------------------------------------------------
  describe('case insensitivity', () => {
    it('handles lowercase grades', () => {
      expect(worstGrade(['a', 'b', 'f'])).toBe('F');
    });

    it('handles mixed-case grades', () => {
      expect(worstGrade(['A', 'b', 'C', 'd'])).toBe('D');
    });

    it('handles lowercase "f" as worst grade', () => {
      expect(worstGrade(['a', 'f'])).toBe('F');
    });
  });

  // -------------------------------------------------------------------------
  // Empty / unknown grade fallback
  // -------------------------------------------------------------------------
  describe('empty and unknown inputs', () => {
    it('returns default "C" for an empty array', () => {
      expect(worstGrade([])).toBe('C');
    });

    it('returns default "C" when all grades are unrecognised', () => {
      expect(worstGrade(['X', 'Z', '?'])).toBe('C');
    });

    it('ignores unrecognised grades and returns worst of known ones', () => {
      // 'X' is unknown; 'B' and 'D' are known — worst is 'D'
      expect(worstGrade(['X', 'B', 'D'])).toBe('D');
    });

    it('returns "A" when list has one valid A and one unknown', () => {
      expect(worstGrade(['A', 'X'])).toBe('A');
    });
  });

  // -------------------------------------------------------------------------
  // Order invariance — result should not depend on array order
  // -------------------------------------------------------------------------
  describe('order invariance', () => {
    const grades = ['C', 'A', 'F', 'B', 'D'];
    const permutations = [
      ['A', 'B', 'C', 'D', 'F'],
      ['F', 'D', 'C', 'B', 'A'],
      ['C', 'A', 'F', 'B', 'D'],
      ['D', 'F', 'A', 'C', 'B'],
    ];

    it.each(permutations)('always returns "F" regardless of order', (...perm) => {
      expect(worstGrade(perm)).toBe('F');
    });
  });
});
