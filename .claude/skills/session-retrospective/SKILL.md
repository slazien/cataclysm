---
name: session-retrospective
description: Use when the user says "wrap up", "reflect", "what did we learn",
  "update your memory", "session retrospective", or at end of a significant
  working session — analyzes the conversation for self-improvement opportunities
---

# Session Retrospective

End-of-session self-improvement ritual. Scans the conversation, applies
learnings to the right memory layer, and reports what changed.
**Non-interactive — auto-apply everything, no approval prompts.**

## Memory Hierarchy

| Layer | Location | What belongs here |
|-------|----------|-------------------|
| **Lessons** | `tasks/lessons.md` | Mistakes, corrections, bugs caused by bad patterns |
| **Workflow rules** | `CLAUDE.md` (project) | Persistent conventions, new process rules, friction fixes |
| **Project facts** | Auto memory (`memory/*.md`) | Architecture facts, debugging insights, recurring context |
| **CLAUDE.md audit** | `CLAUDE.md` (project) | Structural gaps that *caused confusion this session* |

## Phase 1: Scan the Conversation

Look for these signals:
- **Corrections** — User corrected Claude's output, approach, or assumptions
- **Retries** — Claude had to redo something after getting it wrong
- **Friction** — User had to repeat a request or prompt multiple times
- **Explicit rules** — User said "always", "never", "remember to", "don't"
- **Near-misses** — A step that almost introduced a bug or wrong behavior
- **Knowledge gaps** — Facts Claude didn't know that were needed

Skip if: session was short and routine with nothing notable. Say so.

## Phase 2: Classify Each Finding

Use these categories from Post 2's taxonomy:

| Category | Meaning | Action |
|----------|---------|--------|
| **Skill gap** | Claude got something wrong or needed retries | `tasks/lessons.md` |
| **Friction** | Repeated asks, manual steps that should be automatic | `CLAUDE.md` rule |
| **Knowledge** | Project facts Claude should have known | Auto memory |
| **CLAUDE.md gap** | Current instructions caused confusion or wrong behavior | Audit + edit `CLAUDE.md` |
| **Automation** | Repetitive pattern worth making a hook/skill | Note in lessons.md |

## Phase 3: Apply (Auto, No Prompts)

### lessons.md entries
Use this format (matches existing file convention):

```markdown
## [Brief Pattern Title] ([YYYY-MM-DD])

**Pattern**: [Actionable rule — what to always/never do]

**Why**: [Why this matters — consequence of getting it wrong]

**Error signature** (if applicable): [The error message or symptom that signals this]
```

Only add if it's a genuinely new pattern not already in the file.

### CLAUDE.md updates (two cases)

**Case A — Friction/workflow fix:** Add a rule to the most relevant section.
Prefer editing an existing section over adding a new one.

**Case B — Structural gap (Post 1 contribution):** If a section of CLAUDE.md
caused Claude to behave incorrectly or gave insufficient guidance, *revise*
that section — not just append to it. Ask: "Would a staff engineer reading
only CLAUDE.md have known to do this correctly?" If no, improve the section.

### Auto memory
Write a memory file if a project fact was missing that Claude needed.
Keep entries dense: tables and bullets, not prose.

## Phase 4: Report

Present a summary after all changes are applied:

```
Session Retrospective — [date]
──────────────────────────────
Applied:
1. ✅ lessons.md — [brief description of new lesson]
2. ✅ CLAUDE.md §[section] — [what was added/changed and why]
3. ✅ memory/[file].md — [fact recorded]

No action:
- [finding] — already covered in [location]

Commit: chore: session retrospective [date]
```

Commit any modified files with that message.

## What NOT to Do

- Don't append duplicate rules that already exist in CLAUDE.md or lessons.md
- Don't add rules for one-off events that won't recur
- Don't restructure CLAUDE.md wholesale — surgical edits only
- Don't add entries to lessons.md without a concrete "Pattern" and "Why"
- Don't skip the report — even "nothing to learn" sessions should say so
