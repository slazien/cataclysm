# Iteration 3: Golden Examples, XML Tag Structuring, and Advanced Prompt Engineering for Coaching LLMs

**Date:** 2026-03-03
**Focus:** Final research iteration on prompt engineering techniques to maximize coaching quality from Claude Haiku 4.5
**Status:** Complete

---

## Table of Contents
1. [Topic 1: Golden Example Design for Coaching LLMs](#topic-1-golden-example-design-for-coaching-llms)
2. [Topic 2: XML Tag Structuring for Complex Prompts](#topic-2-xml-tag-structuring-for-complex-prompts)
3. [Topic 3: Temperature and Sampling for Factual Coaching](#topic-3-temperature-and-sampling-for-factual-coaching)
4. [Topic 4: Advanced Prompt Techniques for Sports Coaching](#topic-4-advanced-prompt-techniques-for-sports-coaching)
5. [Topic 5: Output Calibration and Grading](#topic-5-output-calibration-and-grading)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Topic 1: Golden Example Design for Coaching LLMs

### Key Findings

#### 1.1 Optimal Number of Examples

Anthropic's official documentation recommends **3-5 examples for best results** ([Prompting best practices - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)). This aligns with our Iteration 2 finding of 2-3 examples but pushes the ceiling higher.

However, research reveals a critical nuance: **quality trumps quantity**. The PromptHub few-shot guide found that "all major models performed better with one shot, but experienced declines when more were included" in certain tasks ([PromptHub: The Few Shot Prompting Guide](https://www.prompthub.us/blog/the-few-shot-prompting-guide)). The 2025 paper "The Few-shot Dilemma" showed that "incorporating excessive domain-specific examples into prompts can paradoxically degrade performance" ([The Few-shot Dilemma: Over-prompting LLMs](https://arxiv.org/html/2509.13196v1)).

**Synthesis for our system:** Since we use Haiku 4.5 (a smaller model), 2-3 examples is likely our sweet spot. The risk with 5 examples is twofold: (a) consuming too many tokens from our context budget, and (b) over-constraining the model's output diversity. Start with 2, validate, add a 3rd only if output variance is too high.

#### 1.2 Full JSON Structure vs Key Fields Only

For structured JSON output, research strongly supports showing the **full JSON structure** in at least one example. Anthropic's documentation states that Claude "replicates naming conventions, code style, formatting, punctuation" from examples ([Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)). For JSON specifically:

- Example 1: Full structure showing complete `priority_corners`, `corner_grades`, `patterns`, and `drills` arrays
- Example 2: Can show abbreviated structure focusing on the hardest-to-get-right fields (grading calibration, causal patterns)

This matches the DigitalOcean recommendation to "use shorter examples" and "summarize" repetitive patterns rather than repeating each one ([DigitalOcean: Few-Shot Prompting](https://www.digitalocean.com/community/tutorials/_few-shot-prompting-techniques-examples-best-practices)).

#### 1.3 Golden Examples vs Contrastive Pairs

Research from Google DeepMind's AuPair framework demonstrates that **systematic selection of example pairs** dramatically outperforms random selection ([Finding Golden Examples: Towards Data Science](https://towardsdatascience.com/finding-golden-examples-a-smarter-approach-to-in-context-learning/)). A 2024 paper on contrastive reasoning showed that LLMs are "decent contrastive reasoners" and that pairing correct and incorrect examples improves accuracy on reasoning tasks ([Large Language Models are Contrastive Reasoners](https://arxiv.org/html/2403.08211v2)).

**For our coaching system, the optimal approach is a hybrid:**
1. **One "gold standard" example** -- a realistic, full coaching report for a driver session demonstrating all desired qualities (OIS format, correct grading, causal patterns, encouragement balance)
2. **One contrastive "anti-example"** -- showing common failure modes with annotations explaining WHY each element is wrong

This contrastive approach is particularly powerful for grading calibration (preventing grade inflation) and for the causal reasoning patterns (showing the difference between "describing WHAT happened" and "diagnosing WHY").

#### 1.4 Realistic vs Synthetic Examples

Research shows synthetic LLM-generated data "can be injected as additional supervision if carefully aligned" but "quality is variable" ([PromptHub Guide](https://www.prompthub.us/blog/the-few-shot-prompting-guide)). The few-shot prompting guide emphasizes that examples should "mirror your actual use case closely" ([Anthropic docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)).

**Recommendation:** Use **semi-realistic synthetic examples** -- designed to illustrate patterns but based on plausible data from real tracks (e.g., Barber Motorsports Park corner profiles). This gives us control over which patterns the example highlights while maintaining realism that the model can generalize from. Fully real examples risk containing too many confounding factors; purely synthetic ones risk teaching the model unrealistic patterns.

### Implementation Recommendations for Our System

1. **Create 2 golden examples** embedded in the system prompt inside `<examples>` tags:
   - Example A: "Strong intermediate driver at Barber" -- shows good OIS format, calibrated grades (mix of A/B/C, no all-A reports), causal patterns, landmark references
   - Example B: "Contrastive anti-example" -- annotated with `[WRONG]` and `[BETTER]` markers showing grade inflation, vague tips, missing causal reasoning

2. **Keep examples compact** -- show full structure for Example A but trim repetitive corner grades to 3 representative entries (one good, one mediocre, one poor corner)

3. **Version the examples** and track output quality metrics per version

### Anti-Patterns to Avoid

- **Over-prompting with examples**: More than 3 examples risks the "few-shot dilemma" where performance degrades
- **Exemplar memorization**: If examples are too specific, the model will parrot them rather than generalize. Vary track names, corner counts, and data ranges between examples
- **Ignoring example order**: Research shows performance is "highly sensitive to which examples you choose, their order, and even minor formatting changes" ([PromptHub](https://www.prompthub.us/blog/the-few-shot-prompting-guide)). Put the best example first
- **Static examples**: Examples should evolve as the system matures. What constitutes a "gold standard" report will change as we add features

---

## Topic 2: XML Tag Structuring for Complex Prompts

### Key Findings

#### 2.1 Anthropic's Latest Guidance on XML Tags

Anthropic's documentation confirms that Claude was **trained specifically to recognize XML tags as a prompt organizing mechanism** ([Use XML tags - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)). Key official guidance:

- "XML tags help Claude parse complex prompts unambiguously, especially when your prompt mixes instructions, context, examples, and variable inputs"
- "Use consistent, descriptive tag names across your prompts"
- "Nest tags when content has a natural hierarchy"
- "There are no special sauce XML tags" -- any meaningful tag names work

The docs specifically recommend wrapping each type of content in its own tag: `<instructions>`, `<context>`, `<input>`.

#### 2.2 Optimal Nesting Depth

Research shows that **balanced complexity** is key. The Medium article on XML in prompt engineering warns that "overly complex structures can make prompts hard to read and debug, so clarity and functional simplicity should be prioritized" ([Effective Prompt Engineering: Mastering XML Tags](https://medium.com/@TechforHumans/effective-prompt-engineering-mastering-xml-tags-for-clarity-precision-and-security-in-llms-992cae203fdc)).

The practical guidance from multiple sources converges on this:
- **1 level of nesting** covers ~80% of use cases (`<task>` wrapping instructions, `<data>` wrapping input)
- **2 levels** is appropriate for hierarchical data (`<documents>` > `<document index="1">`)
- **3+ levels** provides diminishing returns and risks confusing the model

For our coaching prompt, the optimal structure would be:
```xml
<telemetry_data>
  <session_info>...</session_info>
  <corner_analysis>...</corner_analysis>
  <lap_times>...</lap_times>
  <corner_kpis>...</corner_kpis>
  <gains>...</gains>
</telemetry_data>

<coaching_instructions>
  <skill_level>...</skill_level>
  <grading_rubric>...</grading_rubric>
  <output_format>...</output_format>
</coaching_instructions>

<examples>
  <example index="1">...</example>
  <example index="2">...</example>
</examples>
```

#### 2.3 Data Sections vs Instruction Sections

Anthropic's official guidance is definitive on this: **"Put longform data at the top, above your query, instructions, and examples."** Their testing showed that "queries at the end can improve response quality by up to 30%, especially with complex, multi-document inputs" ([Long context tips - Claude API Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)).

**This is the single most impactful structural change we can make.** Our current prompt interleaves data and instructions throughout. Moving to a clear data-first, instructions-last structure aligns with Anthropic's strongest recommendation.

#### 2.4 Prefilling the Assistant Response

**Critical update for our system:** Starting with Claude 4.6, prefilled responses are **no longer supported**. For Haiku 4.5, prefilling `{` to force JSON output is still functional but is a deprecated pattern. Anthropic's migration guidance:

- Use structured outputs (constrained decoding) instead -- now available for Haiku 4.5
- Simply ask the model to output JSON and it will comply reliably
- "Newer models can reliably match complex schemas when told to, especially if implemented with retries"

**Recommendation:** Since we already have retry logic in our validator, we should test removing the `{` prefill (if we use one) and instead rely on structured outputs. Structured outputs guarantee valid JSON conformance via constrained decoding ([Structured outputs - Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)).

#### 2.5 Prompt Ordering Research

Research from the 2025 "Order Effect" paper confirms that **LLMs have historically struggled with order independence**, and reordering elements can cause significant output changes ([The Order Effect](https://arxiv.org/html/2502.04134v2)). The 2024 prompt format sensitivity study found "all p-values below 0.05 in matched pair t-tests assessing model performance sensitivity to prompt format" ([Does Prompt Formatting Have Any Impact on LLM Performance?](https://arxiv.org/pdf/2411.10541)).

**Optimal ordering for our coaching prompt (based on converging research):**
1. Role/system context (in system prompt)
2. Physics reference + guardrails (in system prompt)
3. Knowledge base snippets (in system prompt)
4. Long-form telemetry data (top of user message)
5. Coaching instructions + grading rubric
6. Golden examples
7. Output format specification (at the very end, closest to where generation begins)

### Implementation Recommendations for Our System

**Current state analysis:** Our prompt currently uses markdown headers (`## Corner KPIs`, `## Gain Estimation`) and interleaves data with instructions throughout. The system prompt contains the physics reference and guardrails correctly, but the user message mixes data tables with grading instructions and format specifications without clear separation.

**Proposed restructuring:**

```python
# System prompt (unchanged location, add XML tags):
# <role>...</role>
# <physics_reference>...</physics_reference>
# <guardrails>...</guardrails>
# <knowledge_base>...</knowledge_base>

# User message (restructured):
# <telemetry_data>
#   <session_info>Track, best lap, total laps, corner count</session_info>
#   <corner_analysis>Pre-computed analysis block</corner_analysis>
#   <lap_times>Table</lap_times>
#   <corner_kpis>All-laps KPI table</corner_kpis>
#   <gains>Gain estimation</gains>
#   <optimal>Physics-optimal analysis</optimal>
#   <landmarks>Visual landmarks</landmarks>
#   <equipment>Vehicle + conditions</equipment>
# </telemetry_data>
#
# <coaching_instructions>
#   <skill_level>Novice/Intermediate/Advanced context</skill_level>
#   <analysis_focus>What to analyze across all laps</analysis_focus>
#   <grading_rubric>A-F definitions with behavioral anchors</grading_rubric>
# </coaching_instructions>
#
# <examples>
#   <example index="1">Golden standard report</example>
#   <example index="2">Contrastive anti-example</example>
# </examples>
#
# <output_format>
#   JSON schema + constraints (num corners, speed markers, etc.)
# </output_format>
```

### Anti-Patterns to Avoid

- **Deeply nested XML** (3+ levels) -- diminishing returns, harder to debug
- **Inconsistent tag naming** -- use snake_case consistently (e.g., `<corner_analysis>` not `<CornerAnalysis>`)
- **Mixing markdown headers inside XML tags** -- choose one structural system per section
- **Putting instructions before data** -- Anthropic's own testing shows 30% quality improvement with data-first
- **Relying on prefilling for format control** -- deprecated path, structured outputs are the future

---

## Topic 3: Temperature and Sampling for Factual Coaching

### Key Findings

#### 3.1 Temperature for Factual/Coaching Applications

The research converges on a clear recommendation: **low temperature (0.1-0.3) for structured/factual tasks, moderate temperature (0.5-0.7) for natural coaching prose**.

Key findings:
- "Structured tasks and data extraction require very low temperatures (0.0-0.2) for consistency and reliability" ([LLM Temperature Guide - Tetrate](https://tetrate.io/learn/ai/llm-temperature-guide))
- "Low temperature makes outputs more predictable, not necessarily more true" ([Cognativ](https://www.cognativ.com/blogs/post/what-is-temperature-in-llms-and-its-impact-on-output-quality/315))
- Anthropic specifically recommends "temperature=0 for factual queries" to reduce hallucinations ([Anthropic Avoiding Hallucinations](https://github.com/anthropics/courses/blob/master/prompt_engineering_interactive_tutorial/Anthropic%201P/08_Avoiding_Hallucinations.ipynb))

**Critical insight:** Temperature 0 makes outputs *predictable*, not *accurate*. The accuracy comes from the prompt quality and grounding. Temperature is a consistency lever, not a truth lever.

#### 3.2 Temperature and JSON Parsing Reliability

Research shows that **temperature has minimal effect on JSON validity when using structured outputs or constrained decoding**. Without structured outputs, lower temperature reduces but does not eliminate formatting errors ([Forcing LLM JSON Outputs](https://medium.com/@d.zagirowa/forcing-llm-json-outputs-how-to-make-llm-output-complex-jsons-a8bb00e87f71)).

The best practice: "Use structured outputs (JSON schemas, function calls), then relax temperature for style inside fields where safe" ([Tetrate Guide](https://tetrate.io/learn/ai/llm-temperature-guide)).

**This is a key architectural insight:** With structured outputs handling JSON validity, we can set temperature slightly higher (0.3-0.5) to improve the naturalness of coaching prose inside the JSON string fields, without risking parse failures.

#### 3.3 `top_p` vs `temperature`

Multiple sources converge on this guidance:
- "It is generally recommended to alter temperature or top_p but not both" -- including Anthropic's own guidance for Claude models ([Amazon Bedrock Claude Docs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-claude.html))
- "For factual tasks: low temperature (0.1-0.3), top-p around 0.9" ([Prompt Engineering Guide](https://www.promptingguide.ai/introduction/settings))
- Min-P with values 0.05-0.1 "consistently outperforms Top-P" but is only available in open-source deployments; for commercial APIs like Claude, "Temperature + Top-P" is the recommended combination ([LLM Sampling Parameters Explained](https://www.letsdatascience.com/blog/llm-sampling-temperature-top-k-top-p-and-min-p-explained))

#### 3.4 Optimal Temperature for Accuracy + Natural Prose

The arxiv paper "The Effect of Sampling Temperature on Problem Solving" (2024) found that low temperature is beneficial for structured reasoning but can make prose feel robotic ([Temperature Effects Paper](https://arxiv.org/pdf/2402.05201)).

**Recommendation for our system:** temperature=0.3 with top_p=0.95. This gives:
- Enough determinism for consistent grading (A-F scale won't fluctuate wildly)
- Enough variety for coaching prose to feel natural and personalized
- JSON structure will be handled by structured outputs, making format reliability independent of temperature

#### 3.5 Claude-Specific Temperature Research

Anthropic's hallucination avoidance guide recommends combining low temperature with:
- Explicit permission to say "I don't know" (reduces false confidence)
- Quote extraction before analysis (grounds responses in actual data)
- Multiple complementary techniques rather than relying on temperature alone

Our system already implements the "grounding in data" approach via the pre-computed corner analysis. Adding explicit "admit uncertainty" instructions would be a low-cost improvement.

### Implementation Recommendations for Our System

1. **Set temperature=0.3** (currently we don't set it, which defaults to 1.0 for Claude)
2. **Use structured outputs** for JSON conformance (available on Haiku 4.5 as of 2025)
3. **Do NOT set both temperature and top_p** -- pick temperature as the primary control
4. **Add uncertainty permission**: "If the data is inconclusive for a corner, say so rather than guessing a cause"
5. **Test temperature 0.3 vs 0.5 vs 0.0** on 10 real sessions and compare grade consistency + prose naturalness

### Anti-Patterns to Avoid

- **Temperature 0 everywhere**: Makes prose robotic and formulaic. Coaching needs some naturalness
- **Temperature > 0.7 with JSON output**: Even with structured outputs, higher temperatures increase the chance of hitting edge cases in constrained decoding
- **Setting both temperature and top_p**: These parameters interact in non-obvious ways. Pick one
- **Relying on temperature alone for accuracy**: Temperature controls prediction confidence, not factual grounding. The prompt quality matters more

---

## Topic 4: Advanced Prompt Techniques for Sports Coaching

### Key Findings

#### 4.1 Chain-of-Thought vs Direct Output

The 2025 Wharton study ("Prompting Science Report 2: The Decreasing Value of Chain of Thought in Prompting") provides nuanced findings ([Wharton GAIL](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)):

- CoT "generally improves average performance by a small amount" for non-reasoning models
- But CoT "can introduce more variability in answers, sometimes triggering occasional errors in questions the model would otherwise get right"
- For dedicated reasoning models, "the added benefits of explicit CoT prompting appear negligible"

**For our coaching system:** We use Haiku 4.5, which is NOT a reasoning model (no built-in chain-of-thought). The question is whether to request internal reasoning before the JSON output.

**Recommendation:** Use **structured internal reasoning** via `<thinking>` tags in few-shot examples. Anthropic confirms "multishot examples work with thinking -- use `<thinking>` tags inside your few-shot examples to show Claude the reasoning pattern" ([Anthropic docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)). This lets us guide the reasoning pattern without the cost of explicit CoT in every response.

However, since Haiku 4.5 doesn't support extended thinking, we should use a lighter approach: embed the reasoning PATTERN in the example, showing how to go from data observation to causal diagnosis. The model will internalize this pattern without needing explicit thinking tokens.

#### 4.2 Focused Chain of Thought (FCoT)

We did not find a single canonical "FCoT" paper from 2025. The closest variant is **Analogy-Driven Financial Chain-of-Thought (AD-FCoT)** from 2025, which "integrates analogical reasoning with chain-of-thought prompting" by guiding models to "draw parallels between new events and relevant historical scenarios with known outcomes" ([AD-FCoT](https://arxiv.org/abs/2509.12611)).

The broader 2025 survey "Beyond Chain-of-Thought" catalogs numerous Chain-of-X variants ([ACL 2025](https://aclanthology.org/2025.coling-main.719/)). The key insight is that domain-specific CoT variants outperform generic "let's think step by step" prompting.

**For our system:** We should design a **motorsport-specific reasoning pattern** rather than using generic CoT. Our current OIS format (Observation-Impact-Suggestion) already serves as a domain-specific reasoning framework. This is effectively our own "focused chain of thought" -- we should lean into it harder rather than adopting generic CoT.

#### 4.3 Prompting for Causal Reasoning

Research from 2025 reveals that LLMs "excel at converting telemetry into summaries but struggle with accurate root cause analysis, often hallucinating explanations and confusing symptoms with causes" ([Root Cause Analysis - InfoQ](https://www.infoq.com/articles/causal-reasoning-observability/)). The solution is **task decomposition**: "break root cause finding into steps: interpret anomalies, gather evidence, reason, and generate analysis."

The 2025 Causal-LLM framework presents "a unified one-shot framework for prompt-based causal discovery" ([Causal-LLM](https://aclanthology.org/2025.findings-emnlp.439.pdf)), and ExpliCa evaluates "explicit causal reasoning in LLMs" ([ExpliCa](https://aclanthology.org/2025.findings-acl.891.pdf)).

**Implementation for our system:**
Our current prompt asks the model to "diagnose WHY" in patterns, but doesn't provide a structured causal reasoning framework. We should add:

```
For each pattern, follow this causal chain:
1. OBSERVATION: What measurable telemetry pattern do you see? (cite numbers)
2. MECHANISM: What physics principle explains this? (reference the physics guide)
3. ROOT CAUSE: What is the driver likely DOING to produce this? (technique diagnosis)
4. TIME IMPACT: How much time does this cost? (cite gain data)
5. FIX: What specific change would address the root cause?
```

This decomposition prevents the model from jumping directly from observation to suggestion (skipping the causal mechanism), which is the most common failure mode.

#### 4.4 Empathy/Warmth vs Accuracy Trade-off

The July 2025 Oxford study "Training language models to be warm and empathetic makes them less reliable and more sycophantic" found alarming results ([Too Nice to Be True](https://cognaptus.com/blog/2025-07-30-too-nice-to-be-true-the-reliability-tradeoff-in-warm-language-models/)):

- Warm models showed **+10 to +30 percentage point higher error rates**
- Warm models were **40% more likely to validate incorrect user beliefs** (sycophancy)
- Warm models showed **8-13% higher error rates** across all tasks

Additional research on prompt politeness found that "impolite prompts consistently outperformed polite ones, with accuracy ranging from 80.8% for Very Polite prompts to 84.8% for Very Rude prompts" ([Mind Your Tone](https://arxiv.org/abs/2510.04950)).

**Critical implication for our coaching system:** Our current prompt asks for "approximately 60% positive observations / 40% improvement areas" and to "be encouraging but honest." This warmth instruction could be undermining accuracy.

**Recommended approach:**
- Keep the positive framing requirement BUT constrain it to be data-grounded: "Begin with 2-3 specific data-backed strengths (e.g., 'Your T7 consistency was excellent -- only 0.1s variance')"
- Never ask the model to "be encouraging" in general terms. Instead, specify: "Acknowledge strong corners with specific data, then transition to improvement areas with equal specificity"
- Our OIS format naturally prevents sycophancy because every observation must cite numbers. This is our best defense against the warmth/accuracy trade-off.
- Avoid softening language in the system prompt -- the model should be direct and factual, with warmth expressed through specific praise rather than soft language

#### 4.5 Multi-Level Outputs (Novice vs Advanced)

Research shows that prompt engineering can effectively adapt output complexity using:
- Explicit audience specification: "Explain using terms a [skill level] driver would understand" ([Dextra Labs](https://dextralabs.com/blog/prompt-engineering-for-llm/))
- Dynamic prompt templates that "adapt based on context, reducing ambiguity at runtime" ([Analytics Vidhya](https://www.analyticsvidhya.com/blog/2024/10/17-prompting-techniques-to-supercharge-your-llms/))
- Variable-driven prompts "adaptable to a variety of users without altering fundamental logic" ([Gravitee](https://www.gravitee.io/blog/prompt-engineering-for-llms))

**Our current system handles this well** with the `_SKILL_PROMPTS` dictionary. The improvement opportunity is in the examples: we should have skill-level-specific example outputs that show the appropriate depth and terminology for each level.

### Implementation Recommendations for Our System

1. **Add causal reasoning decomposition** to the prompt (the 5-step chain above)
2. **Embed reasoning patterns in examples** via `<thinking>` tags showing the internal reasoning process
3. **Tighten the warmth/accuracy balance** -- replace "be encouraging" with "cite specific data-backed strengths"
4. **Add an "uncertainty admission" instruction**: "If data is inconclusive for a corner, acknowledge the ambiguity rather than forcing a diagnosis"
5. **Create skill-level-specific example outputs** that demonstrate appropriate depth

### Anti-Patterns to Avoid

- **Generic CoT ("let's think step by step")**: This adds tokens without adding value for domain-specific coaching. Use motorsport-specific reasoning patterns
- **Excessive warmth instructions**: Directly undermines accuracy. Let data-grounded praise handle the positive tone
- **Symptom-as-cause**: "The driver brakes late" is a symptom. "The driver lacks confidence in braking force, so compensates by braking late" is a cause. Prompt for the latter
- **Unsupported causal claims**: The model should never claim a cause it can't support with telemetry data. If brake pressure data isn't available, it shouldn't diagnose brake pressure issues

---

## Topic 5: Output Calibration and Grading

### Key Findings

#### 5.1 Calibrating A-F Grading Scales

The 2025 "Rubric Is All You Need" paper demonstrates that **question-specific (task-specific) rubrics dramatically outperform generic rubrics** for LLM grading ([Rubric Is All You Need](https://arxiv.org/html/2503.23989v1)). The RULERS framework (January 2026) goes further with "locked rubrics and evidence-anchored scoring" that "transforms natural language rubrics into executable specifications" ([RULERS](https://arxiv.org/abs/2601.08654)).

Key research insights:
- "Analytic rubrics with independent scoring of criteria prevent halo effects where strength in one dimension inflates scores in others" ([AutoRubric](https://arxiv.org/html/2603.00077))
- "Ordinal scales with 3-5 levels capture gradations but require careful behavioral anchoring" ([Rubric-Conditioned LLM Grading](https://arxiv.org/html/2601.08843v1))
- "Few-shot calibration is supported by drawing examples from the training split and including them in the prompt" ([LLM-as-a-Judge Guide](https://towardsdatascience.com/llm-as-a-judge-a-practical-guide/))

#### 5.2 Preventing Grade Inflation

The LLM-as-Judge literature identifies systematic biases that directly apply to our grading system:
- **Agreeableness bias**: LLM judges have "true positive rates (TPR > 96%) but very low true negative rates (TNR < 25%)" -- they almost never give bad scores ([Evaluating Scoring Bias](https://arxiv.org/html/2506.22316v1))
- **Verbosity bias**: ~15% inflation from associating longer descriptions with higher quality ([LLM-as-Judge Guide](https://labelyourdata.com/articles/llm-as-a-judge))
- **Self-enhancement bias**: 5-7% boost from models preferring their own style

**Mitigation strategies from the literature:**
1. "Evaluating both (A,B) and (B,A) orderings" for position bias
2. "Using 1-4 scales and rewarding conciseness explicitly" for verbosity bias
3. "Prompt design with concise instructions and explicit bias disclaimers" reduces position and length bias ([Systematic Study of Position Bias](https://aclanthology.org/2025.ijcnlp-long.18.pdf))
4. "Binary outputs tend to produce more stable and reliable evaluations than numeric scoring" ([LLM Judge Evaluation](https://www.emergentmind.com/topics/llm-judge-evaluation))

#### 5.3 Evidence-Anchored Behavioral Rubrics

The most effective approach from the 2025-2026 research is **behavioral anchoring** -- providing explicit descriptions of what each grade level looks like in practice:

Our current rubric:
```
A = very consistent, close to best-lap performance every lap
B = mostly consistent with minor variance
C = moderate variance or a clear technique gap on some laps
D = high variance, inconsistent execution
F = major issue across most laps
```

This is decent but lacks **evidence anchoring** -- specific measurable thresholds that map to each grade. The RULERS framework showed that "reliable LLM judging requires executable rubrics, verifiable evidence, and calibrated scales rather than prompt phrasing alone" ([RULERS](https://arxiv.org/abs/2601.08654)).

#### 5.4 Consistent Grading Across Sessions

Research from AutoSCORE (2025) proposes a "rubric-aligned scoring paradigm that first extracts criterion-specific evidence before scoring, enabling greater consistency, interpretability, and traceability" ([AutoSCORE](https://arxiv.org/html/2509.21910v1)).

The key insight: **Extract evidence first, then grade.** This prevents the model from jumping to a grade and retroactively justifying it. For our system, this means the grading step should explicitly reference the pre-computed statistics before assigning a letter.

### Implementation Recommendations for Our System

**1. Replace the current rubric with evidence-anchored behavioral descriptions:**

```
Grading rubric (each criterion graded independently):

BRAKING:
  A: Brake point std < 3m AND peak brake G within 0.05G of best across 90%+ of laps
  B: Brake point std < 5m AND peak brake G within 0.10G of best across 75%+ of laps
  C: Brake point std 5-8m OR peak brake G spread > 0.15G OR inconsistent on 3+ laps
  D: Brake point std > 8m OR frequently missing braking zone
  F: No consistent brake point established OR dangerous braking patterns

TRAIL BRAKING:
  A: Consistent trail brake application visible in brake-to-turn overlap on 90%+ of laps
  B: Trail braking present on 70%+ of laps with minor timing variance
  C: Trail braking inconsistent or absent on 40%+ of laps
  D: No trail braking detected; abrupt brake release at turn-in on most laps
  N/A: (for novice drivers or flat/lift corners where trail braking is inappropriate)

MIN SPEED:
  A: Min speed std < 1.0 mph AND within 1 mph of target on 90%+ of laps
  B: Min speed std 1.0-2.0 mph AND within 2 mph of target on 75%+ of laps
  C: Min speed std 2.0-3.0 mph OR consistently 3+ mph below target
  D: Min speed std > 3.0 mph OR erratic speed patterns suggesting fear/uncertainty
  F: Min speed consistently 5+ mph below target suggesting fundamental line issues

THROTTLE:
  A: Throttle commit std < 5m AND progressive application on 90%+ of laps
  B: Throttle commit std 5-10m AND mostly progressive application
  C: Throttle commit std 10-15m OR hesitant/partial throttle on 3+ laps
  D: Throttle commit std > 15m OR abrupt on/off throttle patterns
  F: No consistent throttle point OR mid-corner throttle lifts suggesting fear
```

**2. Add grade distribution expectations** to prevent inflation:

```
Grade distribution guidance:
- A typical intermediate driver's report should have mostly B/C grades with 1-2 As and possibly 1-2 Ds
- An all-A report is almost never correct -- it means you are not differentiating performance
- An all-D/F report is also suspect -- even struggling drivers have relative strengths
- The BEST corner for the session might get 1-2 As; the WORST might get 1-2 Ds
- Grade each criterion independently: a corner with great braking can have poor throttle
```

**3. Require evidence extraction before grading:**

```
For each corner grade, you MUST:
1. First cite the specific statistics from the pre-computed analysis (std, mean, best values)
2. Map those statistics to the rubric criteria above
3. THEN assign the grade
Do not assign grades intuitively -- follow the rubric thresholds.
```

### Anti-Patterns to Avoid

- **Vague rubrics**: "Good performance" or "mostly consistent" without measurable thresholds invites grade inflation
- **Holistic grading**: Grading a corner with a single overall score (halo effect). Grade each criterion independently
- **Missing N/A option**: Some criteria don't apply to some corners (trail braking on flat-out kinks). Without an N/A option, the model forces a grade
- **No distribution guidance**: Without an expected distribution, the model defaults to "everyone gets a B+" (agreeableness bias)
- **Retroactive justification**: Grade first, then find evidence to support it. The RULERS framework proves that evidence-first scoring is significantly more reliable

---

## Implementation Roadmap

### Phase 1: Quick Wins (1-2 hours)

1. **Set temperature=0.3** in the API call (currently unset, defaults to 1.0)
2. **Add uncertainty admission** to the system prompt: "If data is inconclusive, acknowledge ambiguity"
3. **Restructure the user message** with XML tags: `<telemetry_data>`, `<coaching_instructions>`, `<output_format>`
4. **Move data to the top** of the user message, instructions + format to the bottom

### Phase 2: Grading Rubric Overhaul (2-3 hours)

5. **Replace the current A-F rubric** with evidence-anchored behavioral descriptions (per Topic 5 recommendations)
6. **Add grade distribution expectations** to prevent inflation
7. **Add evidence-extraction-before-grading instruction**
8. **Add causal reasoning decomposition** (5-step chain from Topic 4)

### Phase 3: Golden Examples (3-4 hours)

9. **Create Example A**: Gold standard coaching report for a realistic intermediate driver session
10. **Create Example B**: Contrastive anti-example with annotated failure modes
11. **Embed examples in `<examples>` tags** in the prompt
12. **Test against 5-10 real sessions** and compare output quality

### Phase 4: Structured Outputs Migration (2-3 hours)

13. **Define a Pydantic schema** for the coaching report JSON (matches existing `CoachingReport` dataclass)
14. **Migrate from prompt-based JSON** to structured outputs API parameter
15. **Test JSON conformance** -- should be 100% with structured outputs
16. **Relax temperature** to 0.4-0.5 once JSON is guaranteed (improves prose quality)

### Phase 5: Validation & Tuning (ongoing)

17. **A/B test old vs new prompt** on 20 sessions
18. **Measure grade distribution** -- should see a bell curve around B/C, not clustering at A/B
19. **Review causal reasoning quality** -- do patterns explain WHY, not just WHAT?
20. **Iterate on examples** based on output quality metrics

---

## Sources

### Topic 1: Golden Examples
- [PromptHub: The Few Shot Prompting Guide](https://www.prompthub.us/blog/the-few-shot-prompting-guide)
- [Finding Golden Examples: Towards Data Science](https://towardsdatascience.com/finding-golden-examples-a-smarter-approach-to-in-context-learning/)
- [Large Language Models are Contrastive Reasoners (2024)](https://arxiv.org/html/2403.08211v2)
- [DigitalOcean: Few-Shot Prompting](https://www.digitalocean.com/community/tutorials/_few-shot-prompting-techniques-examples-best-practices)
- [The Few-shot Dilemma: Over-prompting LLMs (2025)](https://arxiv.org/html/2509.13196v1)
- [LangChain: Few-shot for Tool Calling](https://blog.langchain.com/few-shot-prompting-to-improve-tool-calling-performance/)

### Topic 2: XML Tag Structuring
- [Anthropic: Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/use-xml-tags)
- [Anthropic: Long Context Tips](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)
- [Anthropic: Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic: Increase Output Consistency](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/increase-consistency)
- [Effective Prompt Engineering: Mastering XML Tags (Medium)](https://medium.com/@TechforHumans/effective-prompt-engineering-mastering-xml-tags-for-clarity-precision-and-security-in-llms-992cae203fdc)
- [Structured Prompting Techniques: XML & JSON Guide](https://codeconductor.ai/blog/structured-prompting-techniques-xml-json/)
- [Why XML Tags Are Fundamental to Claude](https://glthr.com/XML-fundamental-to-Claude)
- [Does Prompt Formatting Have Any Impact on LLM Performance? (2024)](https://arxiv.org/pdf/2411.10541)
- [The Order Effect (2025)](https://arxiv.org/html/2502.04134v2)

### Topic 3: Temperature and Sampling
- [LLM Temperature Guide (Tetrate)](https://tetrate.io/learn/ai/llm-temperature-guide)
- [Temperature and Output Quality (Cognativ)](https://www.cognativ.com/blogs/post/what-is-temperature-in-llms-and-its-impact-on-output-quality/315)
- [Anthropic: Avoiding Hallucinations (Course)](https://github.com/anthropics/courses/blob/master/prompt_engineering_interactive_tutorial/Anthropic%201P/08_Avoiding_Hallucinations.ipynb)
- [IBM: What is LLM Temperature?](https://www.ibm.com/think/topics/llm-temperature)
- [The Effect of Sampling Temperature on Problem Solving (2024)](https://arxiv.org/pdf/2402.05201)
- [Forcing LLM JSON Outputs (Medium)](https://medium.com/@d.zagirowa/forcing-llm-json-outputs-how-to-make-llm-output-complex-jsons-a8bb00e87f71)
- [LLM Sampling Parameters Explained](https://www.letsdatascience.com/blog/llm-sampling-temperature-top-k-top-p-and-min-p-explained)
- [Complete Guide: Temperature and Top-p](https://promptengineering.org/prompt-engineering-with-temperature-and-top-p/)
- [Zero-Error JSON with Claude (Medium)](https://medium.com/@meshuggah22/zero-error-json-with-claude-how-anthropics-structured-outputs-actually-work-in-real-code-789cde7aff13)

### Topic 4: Advanced Prompt Techniques
- [Wharton: The Decreasing Value of Chain of Thought (2025)](https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/)
- [Prompting Science Report 2 (arXiv)](https://arxiv.org/abs/2506.07142)
- [Too Nice to Be True: Warmth-Reliability Trade-off (2025)](https://cognaptus.com/blog/2025-07-30-too-nice-to-be-true-the-reliability-tradeoff-in-warm-language-models/)
- [Training LMs to be Warm Makes Them Less Reliable (arXiv)](https://arxiv.org/abs/2507.21919)
- [Mind Your Tone: Prompt Politeness Affects LLM Accuracy (2025)](https://arxiv.org/abs/2510.04950)
- [Does Tone Change the Answer? (2025)](https://arxiv.org/html/2512.12812v1)
- [Causal-LLM: Unified Framework for Causal Discovery (2025)](https://aclanthology.org/2025.findings-emnlp.439.pdf)
- [How Causal Reasoning Addresses LLM Limitations (InfoQ)](https://www.infoq.com/articles/causal-reasoning-observability/)
- [Beyond Chain-of-Thought: Chain-of-X Survey (2025)](https://aclanthology.org/2025.coling-main.719/)
- [AD-FCoT: Analogy-Driven Chain-of-Thought (2025)](https://arxiv.org/abs/2509.12611)

### Topic 5: Grading and Calibration
- [Rubric Is All You Need (2025)](https://arxiv.org/html/2503.23989v1)
- [RULERS: Locked Rubrics and Evidence-Anchored Scoring (2026)](https://arxiv.org/abs/2601.08654)
- [AutoRubric: Unified Framework for Rubric-Based LLM Evaluation (2026)](https://arxiv.org/html/2603.00077)
- [Rubric-Conditioned LLM Grading (2025)](https://arxiv.org/html/2601.08843v1)
- [AutoSCORE: Multi-Agent Automated Scoring (2025)](https://arxiv.org/html/2509.21910v1)
- [LLM-as-a-Judge: A Practical Guide (Towards Data Science)](https://towardsdatascience.com/llm-as-a-judge-a-practical-guide/)
- [Evaluating Scoring Bias in LLM-as-a-Judge (2025)](https://arxiv.org/html/2506.22316v1)
- [Systematic Study of Position Bias in LLM-as-a-Judge (2025)](https://aclanthology.org/2025.ijcnlp-long.18.pdf)
- [LLM-as-a-Judge Guide (Label Your Data)](https://labelyourdata.com/articles/llm-as-a-judge)
- [Confusion-Aware Rubric Optimization (2026)](https://arxiv.org/html/2603.00451)
- [LLM Rubric (Promptfoo)](https://www.promptfoo.dev/docs/configuration/expected-outputs/model-graded/llm-rubric/)
