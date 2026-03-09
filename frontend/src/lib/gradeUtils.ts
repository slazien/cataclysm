const GRADE_ORDER = ['A', 'B', 'C', 'D', 'F'] as const;

const NA_VALUES = new Set(['N/A', 'NA', '—', '-']);

/** Check if a grade string represents N/A (not applicable). */
export function isNAGrade(grade: string): boolean {
  return NA_VALUES.has(grade.trim().toUpperCase());
}

/** Returns the worst (highest-index) grade from the provided grade letters, ignoring N/A. */
export function worstGrade(grades: string[]): string {
  let worstIdx = -1;
  for (const g of grades) {
    if (isNAGrade(g)) continue;
    const idx = GRADE_ORDER.indexOf(g.toUpperCase() as (typeof GRADE_ORDER)[number]);
    if (idx > worstIdx) worstIdx = idx;
  }
  return worstIdx >= 0 ? GRADE_ORDER[worstIdx] : 'C';
}
