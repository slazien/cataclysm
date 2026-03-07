export const colors = {
  bg: { base: '#0a0c10', surface: '#13161c', elevated: '#1c1f27', overlay: '#252830' },
  text: { primary: '#e2e4e9', secondary: '#8b919e', muted: '#555b67' },
  motorsport: { brake: '#ef4444', throttle: '#22c55e', pb: '#a855f7', optimal: '#3b82f6', neutral: '#f59e0b' },
  grade: { a: '#22c55e', b: '#84cc16', c: '#f59e0b', d: '#f97316', f: '#ef4444' },
  ai: { bg: 'rgba(99, 102, 241, 0.06)', icon: '#818cf8', borderFrom: '#6366f1', borderTo: '#a855f7' },
  accent: { primary: '#f59e0b', primaryHover: '#d97706', data: '#3b82f6', dataHover: '#2563eb' },
  lap: ['#58a6ff', '#f97316', '#22c55e', '#e879f9', '#facc15', '#06b6d4', '#f87171', '#a3e635'],
  comparison: { reference: '#58a6ff', compare: '#f97316' },
  cursor: 'rgba(255, 255, 255, 0.6)',
  grid: '#252830',
  axis: '#8b919e',
} as const;

export const fonts = {
  sans: "'Inter', system-ui, -apple-system, sans-serif",
  display: "'Barlow Semi Condensed', 'Inter', system-ui, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', monospace",
} as const;

/** Shared motion config — durations in seconds, spring configs for motion (Framer Motion) */
export const motion = {
  /** View switch cross-fade */
  viewTransition: { duration: 0.2, ease: [0.25, 0.1, 0.25, 1] as const },
  /** Card entrance stagger */
  stagger: { staggerChildren: 0.05 },
  cardEntrance: { duration: 0.3, ease: 'easeOut' as const },
  /** Lap pill press feedback */
  pillPress: { type: 'spring' as const, stiffness: 400, damping: 25 },
  /** PB celebration pulse */
  pbPulse: { duration: 0.6, ease: 'easeInOut' as const },
  /** Chart line draw */
  chartDraw: { duration: 0.5 },
  /** Grade chip stagger */
  gradeStagger: { staggerChildren: 0.04 },
  gradeChip: { duration: 0.2, ease: 'easeOut' as const },
} as const;
