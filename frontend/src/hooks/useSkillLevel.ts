import { useUiStore, type SkillLevel } from '@/stores/uiStore';

type SkillFeature =
  | 'sectors_tab'
  | 'custom_tab'
  | 'replay_tab'
  | 'heatmap'
  | 'boxplot'
  | 'absolute_distances'
  | 'relative_distances'
  | 'grade_explanations'
  | 'guided_prompts'
  | 'raw_data_table'
  | 'keyboard_overlay'
  | 'delta_breakdown'
  | 'gforce_analysis';

// Feature visibility matrix: true = visible at this skill level
const FEATURE_MATRIX: Record<SkillFeature, Record<SkillLevel, boolean>> = {
  sectors_tab:        { novice: false, intermediate: true,  advanced: true },
  custom_tab:         { novice: false, intermediate: false, advanced: true },
  replay_tab:         { novice: false, intermediate: true,  advanced: true },
  heatmap:            { novice: false, intermediate: true,  advanced: true },
  boxplot:            { novice: false, intermediate: true,  advanced: true },
  absolute_distances: { novice: false, intermediate: true,  advanced: true },
  relative_distances: { novice: true,  intermediate: true,  advanced: false },
  grade_explanations: { novice: true,  intermediate: false, advanced: false },
  guided_prompts:     { novice: true,  intermediate: true,  advanced: false },
  raw_data_table:     { novice: false, intermediate: false, advanced: true },
  keyboard_overlay:   { novice: false, intermediate: false, advanced: true },
  delta_breakdown:    { novice: false, intermediate: true,  advanced: true },
  gforce_analysis:    { novice: false, intermediate: false, advanced: true },
};

export function useSkillLevel() {
  const skillLevel = useUiStore((s) => s.skillLevel);

  return {
    skillLevel,
    isNovice: skillLevel === 'novice',
    isIntermediate: skillLevel === 'intermediate',
    isAdvanced: skillLevel === 'advanced',
    showFeature: (feature: SkillFeature) => FEATURE_MATRIX[feature][skillLevel],
  };
}

export type { SkillFeature };
