export const colors = {
  bg: { base: '#0a0c10', surface: '#13161c', elevated: '#1c1f27', overlay: '#252830' },
  text: { primary: '#e2e4e9', secondary: '#8b919e', muted: '#555b67' },
  motorsport: { brake: '#ef4444', throttle: '#22c55e', pb: '#a855f7', optimal: '#3b82f6', neutral: '#f59e0b' },
  grade: { a: '#22c55e', b: '#84cc16', c: '#f59e0b', d: '#f97316', f: '#ef4444' },
  ai: { bg: 'rgba(99, 102, 241, 0.06)', icon: '#818cf8', borderFrom: '#6366f1', borderTo: '#a855f7' },
  lap: ['#58a6ff', '#f97316', '#22c55e', '#e879f9', '#facc15', '#06b6d4', '#f87171', '#a3e635'],
  comparison: { reference: '#58a6ff', compare: '#f97316' },
  cursor: 'rgba(255, 255, 255, 0.25)',
  grid: '#1c1f27',
  axis: '#555b67',
} as const;

export const fonts = {
  sans: "'Inter', system-ui, -apple-system, sans-serif",
  mono: "'JetBrains Mono', 'SF Mono', monospace",
} as const;
