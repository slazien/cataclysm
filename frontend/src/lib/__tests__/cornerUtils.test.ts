import { parseCornerNumber } from '../cornerUtils';

// parseCornerNumber extracts the first run of digits from a corner ID string.
// Returns the integer if found, null otherwise.

describe('parseCornerNumber', () => {
  // -------------------------------------------------------------------------
  // Standard "T<N>" format
  // -------------------------------------------------------------------------
  describe('standard T-prefix format', () => {
    it('parses "T1" -> 1', () => {
      expect(parseCornerNumber('T1')).toBe(1);
    });

    it('parses "T5" -> 5', () => {
      expect(parseCornerNumber('T5')).toBe(5);
    });

    it('parses "T10" -> 10', () => {
      expect(parseCornerNumber('T10')).toBe(10);
    });

    it('parses "T12" -> 12', () => {
      expect(parseCornerNumber('T12')).toBe(12);
    });

    it('parses "T0" -> 0', () => {
      expect(parseCornerNumber('T0')).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // Lowercase and mixed-case prefixes
  // -------------------------------------------------------------------------
  describe('case variants', () => {
    it('parses lowercase "t5" -> 5', () => {
      expect(parseCornerNumber('t5')).toBe(5);
    });

    it('parses "turn5" -> 5', () => {
      expect(parseCornerNumber('turn5')).toBe(5);
    });

    it('parses "TURN10" -> 10', () => {
      expect(parseCornerNumber('TURN10')).toBe(10);
    });
  });

  // -------------------------------------------------------------------------
  // Numeric-only strings
  // -------------------------------------------------------------------------
  describe('numeric-only strings', () => {
    it('parses "5" -> 5', () => {
      expect(parseCornerNumber('5')).toBe(5);
    });

    it('parses "12" -> 12', () => {
      expect(parseCornerNumber('12')).toBe(12);
    });

    it('parses "0" -> 0', () => {
      expect(parseCornerNumber('0')).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // Alternative prefix formats
  // -------------------------------------------------------------------------
  describe('alternative formats', () => {
    it('parses "Corner3" -> 3', () => {
      expect(parseCornerNumber('Corner3')).toBe(3);
    });

    it('parses "C7" -> 7', () => {
      expect(parseCornerNumber('C7')).toBe(7);
    });

    it('extracts first digit group from "T5-T6" -> 5', () => {
      expect(parseCornerNumber('T5-T6')).toBe(5);
    });

    it('handles prefix with leading zeros in number "T03" -> 3', () => {
      expect(parseCornerNumber('T03')).toBe(3);
    });
  });

  // -------------------------------------------------------------------------
  // Large numbers
  // -------------------------------------------------------------------------
  describe('large corner numbers', () => {
    it('parses "T100" -> 100', () => {
      expect(parseCornerNumber('T100')).toBe(100);
    });

    it('parses "T999" -> 999', () => {
      expect(parseCornerNumber('T999')).toBe(999);
    });
  });

  // -------------------------------------------------------------------------
  // Invalid inputs — should return null
  // -------------------------------------------------------------------------
  describe('invalid inputs returning null', () => {
    it('returns null for empty string', () => {
      expect(parseCornerNumber('')).toBeNull();
    });

    it('returns null for letters-only string', () => {
      expect(parseCornerNumber('abc')).toBeNull();
    });

    it('returns null for special-character-only string', () => {
      expect(parseCornerNumber('!@#')).toBeNull();
    });

    it('returns null for a hyphen-only string', () => {
      expect(parseCornerNumber('-')).toBeNull();
    });

    it('returns null for string with only spaces', () => {
      expect(parseCornerNumber('   ')).toBeNull();
    });
  });
});
