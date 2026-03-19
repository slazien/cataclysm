# Model Comparison Report — 2026-03-19

> Comparative evaluation of 6 OpenAI GPT models for coaching report generation.
> Conversation: `20e087c7-ffd8-48b6-b8f8-74e8ebb5818e`

## Overview
- Sessions: 4 (amp_full_20260315, barber_20260222, roebling_20260111, amp_full_20251214)
- Skill levels: novice, intermediate, advanced
- Models: 6
- Total calls: 72
- Total cost: $1.0048
- Eval framework: deterministic only (no LLM judge) — schema, physics guardrails, citation grounding, per-corner attribution, drills quality

## Results Summary

| Model | Avg Score | Pass Rate | Avg Cost | Avg Latency | Avg Input Tok | Avg Output Tok | Errors |
|-------|-----------|-----------|----------|-------------|---------------|----------------|--------|
| gpt-5.4-nano | 0.912 | 100% | $0.00907 | 21.7s | 18052 | 4368 | 0 |
| gpt-4.1-mini | 0.831 | 83% | $0.01264 | 52.3s | 18053 | 3386 | 0 |
| gpt-4.1-nano | 0.800 | 33% | $0.00262 | 17.5s | 18053 | 2044 | 0 |
| gpt-5.4-mini | 0.786 | 67% | $0.03221 | 17.3s | 18053 | 4149 | 0 |
| gpt-5-nano | 0.727 | 8% | $0.00585 | 85.3s | 18052 | 12369 | 0 |
| gpt-5-mini | 0.556 | 67% | $0.02134 | 129.3s | 18052 | 8412 | 0 |

## Per-Dimension Scores

| Model | array_bounds | because_clauses | citation_grounding | corner_first | drills_quality | grade_values | json_valid | per_corner_attribution | physics_guardrails | priority_corner_structure | required_fields | summary_length |
|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|-------|
| gpt-5.4-nano | 1.000 | 0.972 | 0.715 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| gpt-4.1-mini | 1.000 | 1.000 | 0.541 | 0.688 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| gpt-4.1-nano | 1.000 | 0.917 | 0.390 | 1.000 | 0.917 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| gpt-5.4-mini | 1.000 | 0.856 | 0.571 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.917 | 1.000 |
| gpt-5-nano | 1.000 | 0.410 | 0.288 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| gpt-5-mini | 1.000 | 0.781 | 0.518 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.667 | 1.000 | 1.000 |

## Cost Analysis

### Pricing Used (per 1M tokens)

| Model | Input | Output |
|-------|-------|--------|
| gpt-4.1-mini | $0.40 | $1.60 |
| gpt-4.1-nano | $0.10 | $0.40 |
| gpt-5-mini | $0.25 | $2.00 |
| gpt-5-nano | $0.05 | $0.40 |
| gpt-5.4-mini | $0.75 | $4.50 |
| gpt-5.4-nano | $0.20 | $1.25 |

### Cost-Quality Tradeoff

| Model | Avg Score | Avg Cost | Score per $0.01 |
|-------|-----------|----------|-----------------|
| gpt-5.4-nano | 0.912 | $0.00907 | 1.01 |
| gpt-4.1-mini | 0.831 | $0.01264 | 0.66 |
| gpt-4.1-nano | 0.800 | $0.00262 | 3.05 |
| gpt-5.4-mini | 0.786 | $0.03221 | 0.24 |
| gpt-5-nano | 0.727 | $0.00585 | 1.24 |
| gpt-5-mini | 0.556 | $0.02134 | 0.26 |

## Execution Notes

- First run: all 72 calls errored ("Unsupported model") — model IDs were wrong
- Second run: errored again (likely same issue or API key/config)
- Third run: succeeded — all 72 calls completed, 0 errors
- Report originally written to `data/smoke_report.md` in a worktree (since cleaned up)
- Comparison script: `scripts/model_comparison.py` (also in cleaned-up worktree)

## Recommendation

- **Best quality**: gpt-5.4-nano (score=0.912, 100% pass rate)
- **Best value**: gpt-4.1-nano (score=0.800, cost=$0.00262 — 3.05 score/$0.01)
- **Cheapest**: gpt-4.1-nano ($0.00262/call)
- **Recommended for production**: gpt-5.4-nano — highest quality AND only model with 100% pass rate

### Key Differentiators
- `citation_grounding` was the main separator — models that accurately cited telemetry data scored much higher
- `because_clauses` (physics reasoning) was the second differentiator
- All models passed structural checks (JSON, schema, physics guardrails) — quality gap is in the "soft" dimensions
- Older gpt-5-mini was worst performer (0.556) despite being more expensive than gpt-5.4-nano
- Newer generation (5.4) nano dramatically outperformed older generation (5) models
