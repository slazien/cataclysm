const GRADE_ORDER = ['A', 'B', 'C', 'D', 'F'] as const;

/** Returns the worst (highest-index) grade from the provided grade letters. */
export function worstGrade(grades: string[]): string {
  let worstIdx = -1;
  for (const g of grades) {
    const idx = GRADE_ORDER.indexOf(g.toUpperCase() as (typeof GRADE_ORDER)[number]);
    if (idx > worstIdx) worstIdx = idx;
  }
  return worstIdx >= 0 ? GRADE_ORDER[worstIdx] : 'C';
}
