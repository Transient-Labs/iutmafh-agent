# Paper Update Plan — swap Claude models to Sonnet 4.6 + Sonnet 5 (reasoning on)

> **How to use this doc:** point a fresh Claude session here once the new Claude
> data is collected and verified. This file is self-contained — read it top to
> bottom, then execute Steps 1–7 in order. Do NOT start until the data
> prerequisite below is met. The `## Constraints` section is binding.

Durable handoff so this survives a session close. Goal: update the whitepaper
(`whitepaper-v1.html` + standalone) and the slide deck (`whitepaper-v1-slides.html`
+ standalone) so the **Anthropic family is Claude Sonnet 4.6 (economical) and
Claude Sonnet 5 (flagship)**, replacing Claude Haiku 4.5. Same paper structure,
sections, and figure set — only the Claude family and its numbers change. Keep it
reading as though these were always the two Claude models.

## Three coupled changes

1. **Model swap.** Remove `claude-haiku-4-5`. Claude family becomes
   `claude-sonnet-4-6` (economical tier) and `claude-sonnet-5` (flagship tier),
   framed as the economical vs flagship model of the same generation (not a clean
   cost split like Haiku-vs-Sonnet, so word the tier framing deliberately).
2. **Reasoning ON.** The new Claude data is collected with extended thinking
   enabled (see `review.py` `claude_thinking_kwargs`; adaptive for Sonnet 5,
   budgeted for Sonnet 4.6). GPT and Gemini already reason at their defaults, so
   this makes all three families reason. NOTE the earlier 6-model study had Claude
   non-reasoning — the new Claude runs are NOT comparable to the old
   experiment-5/6 data, which is why both are being re-run fresh.
3. **Rename "frontier" → "flagship" everywhere in the paper.** "Frontier" implies
   experimental/bleeding-edge, which is not the intent. Keep the low tier worded
   **"economical"** (the paper's existing term), not "economic".

## Data prerequisite (user is running this)

Re-run BOTH prompts for BOTH new Claude models, reasoning on:
- `experiment-5` (review_prompt 4) → `claude-sonnet-4-6`, `claude-sonnet-5`
- `experiment-6` (review_prompt 5) → `claude-sonnet-4-6`, `claude-sonnet-5`

**Two traps that make "just overwrite the dirs" wrong:**
1. **Reasoning state is NOT recorded in the results JSON** (workbook block stores
   models, sampling_knobs, review_prompt, system_prompt — no thinking field). So
   the new reasoning-on Sonnet 4.6 is indistinguishable by metadata from the old
   non-reasoning Sonnet 4.6 (same model ID).
2. **Resume keys on `(condition, preference_variant, model, run)`**, not on
   reasoning. Running into the existing `experiment-6` would see the old
   `claude-sonnet-4-6` slots as already complete and SKIP them, keeping stale
   non-reasoning data. Old Haiku reviews would also linger in the file.

Also: the export/discovery (`compare_dashboards`) scans EVERY `results/experiment-*/`
dir, so any leftover Haiku reviews there would surface as a 7th model.

**Recommended procedure (cleanest):**
1. Move old `results/experiment-5` and `experiment-6` to `results/archive-<name>/`
   (outside the `experiment-*` glob) — preserves the old Haiku + non-reasoning
   data AND removes it from discovery.
2. Create fresh, EMPTY `results/experiment-5` (prompt 4) and `experiment-6`
   (prompt 5).
3. Run the new Sonnet 4.6 + Sonnet 5 (reasoning on) into the fresh dirs. Fresh =
   nothing to resume onto, so no stale slots. Reusing the names keeps the
   `paper_figures.py` `fig10_invented` map (`experiment-5: 4`, `experiment-6: 5`)
   correct — no code change.
   (New dir names would work but require archiving old 5/6 out of the glob AND
   updating that hardcoded map — more work, no benefit.)

Each experiment should end up with 792 reviews (22 artworks × 6 condition-slots ×
3 runs × 2 models), 0 null verdicts, every slot 3 runs. Verify before any paper
work (the flat-schema + reasoning fixes should keep verdicts clean).

Optional harness improvement worth doing first: record the reasoning/thinking
config in the workbook block of the results JSON (currently unrecorded), so
reasoning-on vs -off runs are distinguishable for provenance.

## Steps

### 1. Regenerate source-of-truth CSVs
Run `art_reviewer_sdk/export_whitepaper.py` (data-driven; `model_family` splits on
`-` so `claude-sonnet-5` → family `claude` automatically). Place regenerated
`reviews.csv`, `rationales.csv`, `aggregates.md`, `metadata.md` into
`whitepaper_info/`. Confirm: 6 experiments, family `claude` present, ~4,752 rows,
models are the new set (no `claude-haiku-4-5`), 0 errors.

### 2. Update `art_reviewer_sdk/paper_figures.py` constants
Replace `claude-haiku-4-5` with `claude-sonnet-5` and re-map tiers. Exact spots:
- `MODEL_ORDER` (~L27-29): `... "claude-sonnet-4-6", "claude-sonnet-5"` (economical
  then flagship, matching table order).
- `MODEL_LABEL` (~L30-35): drop Haiku; add `"claude-sonnet-5": "Claude Sonnet 5"`;
  keep `"claude-sonnet-4-6": "Claude Sonnet 4.6"`.
- `MODEL_COLOR` (~L39-41): give economical Sonnet 4.6 the lighter green
  (`#74c493`) and flagship Sonnet 5 the darker green (`#2e7d4f`) — i.e. swap the
  shades so darker = flagship, consistent with the other families.
- `FAMILY_OF` (~L267-269): `"claude-sonnet-5": "Claude"` (keep sonnet-4-6).
- `TIER_MARKER` (~L270-271): Sonnet 4.6 → `"o"` (economical), Sonnet 5 → `"s"`
  (flagship). Update the trailing `# economic` / `# frontier` comments to
  `# economical` / `# flagship`.
- Label-nudge dict (~L275): replace the `claude-haiku-4-5` key with
  `claude-sonnet-5`; tune offsets so labels don't collide (Sonnet 5 may sit near
  Sonnet 4.6).
- Fig8 legend labels (~L296/298): `"Economic tier"` → `"Economical"`,
  `"Frontier tier"` → `"Flagship"`.
- Comment L26: "economic then frontier" → "economical then flagship".
Regenerate all figures with `uv run --with matplotlib python art_reviewer_sdk/paper_figures.py`
(or the project's usual invocation). Confirm all render with the six models, no
KeyError, no crowding (fig2/3/4/7/10 legends).

### 3. frontier → flagship rename (SURGICAL — data is off-limits)
"frontier" appears ~258 times, but **211 are in `results/**` and
`rationales.csv` as model output** (models literally wrote "frontier" in
critiques) — NEVER rename those. Rename only our tier label in:
- `whitepaper_info/whitepaper-v1.html` (14 hits — prose "an economical and a
  frontier model", `Frontier` table cells, "the frontier models")
- `whitepaper_info/whitepaper-v1-slides.html` (2 — the tier label)
- `art_reviewer_sdk/paper_figures.py` (3 — done in step 2)
- optional older docs: `whitepaper.html` (8), `paperDetails.md` (4)
Check each hit is our label, not a quoted model word, before replacing.

### 4. Recompute every Claude stat and re-attribute superlatives
`reviews.csv` is the ONLY quantitative source — recompute, never estimate. Write a
fresh recompute script (the prior session's `recompute*.py` in scratchpad are
gone). Recompute: Table 2 (unanimous by prompt×tier×model, 12 rows), Table 3,
Table 4 (artwork×model — re-pick the 8 least-consistent), Table 8 scorecard (mean,
acquire, agreement, swing, scale-spread per model), Table 9 + mismatch totals,
pooled context effects (Table 5), description/canonical tables (6/7), the 4.3
prompt-effect pooled means, group counts, and EVERY superlative (steadiest,
harshest, loosest, most-reserved, longest reviews, most absolute language,
invented-buyer leader, most/least recognized, Artwork 012 reversal). With Haiku
gone and Sonnet 5 in, several superlatives will re-attribute — check all of them.

### 5. Rewrite `whitepaper-v1.html`
Using recomputed numbers, keep structure/sections/figures identical:
- Reframe the Claude family as Sonnet 4.6 (economical) + Sonnet 5 (flagship);
  update Abstract, Intro, Sec 3 (design), Sec 4 intro, Discussion.
- Update every per-model table (2, 3, 4, 8, 9) with the new Claude rows/values;
  update pooled numbers in Tables 5-7 and captions.
- Rewrite the 4.4 tier finding honestly for the new pairing (recompute whether
  bigger=harsher still holds for Claude; the old Haiku/Sonnet flip may change).
- Update the Claude writing-style comparison, Fig 8 caption, and any figure
  captions naming models/values (Figs 1, 4, 6, 8).
- 4.5: revisit the "Claude Haiku couldn't follow the format" note — with Haiku
  gone AND the flat-schema fix in place, this likely gets removed or rewritten.
- Apply frontier→flagship (step 3).
- Totals stay 4,752 reviews / 1,584 complete groups (unchanged model count = 6).

### 6. Regenerate `whitepaper-v1-standalone.html`
Re-embed all figures as base64 from the updated `whitepaper-v1.html`. Regeneration
pattern (base64 every non-data/non-http `src`), then byte-verify it's in sync.

### 7. Update the slide deck + its standalone
`whitepaper-v1-slides.html` is a 19-section scroll deck. Exact slides that name a
Claude model, a tier label, or a Claude superlative (recompute all against the new
CSV, don't reuse the old wording):
- **Slide 3 (Design):** the `.models` block — economical row becomes
  `GPT-5 Mini · Gemini 2.5 Flash · Claude Sonnet 4.6`, flagship row
  `GPT-5 · Gemini 3 Flash Preview · Claude Sonnet 5`; rename the `Frontier` tier
  label to `Flagship`; and the take line "an economical and a frontier tier" →
  "economical and a flagship tier".
- **Slide 7 (Consistency numbers):** rewrite "Claude Sonnet was the exception…
  Claude Haiku swung the widest" — Haiku is gone, so re-derive who is most
  consistent and who swings widest from the new data.
- **Slide 13 (Temperament / Fig 8):** re-check "Claude harshest of all" and the
  "six personalities" takeaway against recomputed numbers.
- **Slide 15 (More quirks):** REMOVE or rewrite the bullet "Claude Haiku alone
  kept returning reviews with no score at all" — Haiku is dropped AND that
  format-compliance problem was fixed by the flat-schema change in `review.py`, so
  the claim no longer applies to any model in the set.
- Re-verify Figs 1/5/7/8/9 (referenced from `figures/`) still illustrate the point
  after regeneration; update any figure caption that names a value.
- Regenerate `whitepaper-v1-slides-standalone.html` (base64-embed the six images),
  then byte-verify it's in sync with the source.

## Files touched
- `whitepaper_info/reviews.csv`, `rationales.csv`, `aggregates.md`, `metadata.md` (regenerated)
- `art_reviewer_sdk/paper_figures.py` (constants + legend labels)
- `whitepaper_info/figures/*.png` (regenerated)
- `whitepaper_info/whitepaper-v1.html` + `whitepaper-v1-standalone.html`
- `whitepaper_info/whitepaper-v1-slides.html` + `whitepaper-v1-slides-standalone.html`
- `results/experiment-5/`, `results/experiment-6/` (new Claude data; old archived)

## Verification checklist
1. CSV: 6 experiments, no `claude-haiku-4-5`, `claude-sonnet-5` present, ~4,752 rows, 0 errors.
2. Hand-check 2-3 recomputed numbers against the CSV (a Claude Table 2 row; the 4.3 pooled prompt effect).
3. Figures: all render, six models, no KeyError, no legend crowding.
4. Grep final HTML for stale `Haiku`, `frontier` (as our label), and any superlative still crediting a removed/wrong model — none should remain.
5. Standalones byte-in-sync with their sources; all figures embedded and rendering.
6. Slides + slides-standalone updated and in sync.

## Constraints (unchanged, MUST hold)
- `reviews.csv` is the ONLY quantitative source. Recompute every stat; never reuse
  remembered numbers.
- Writing rules: NO em dashes; avoid the "It is not about X. It is about Y." AI
  cliché; observations before interpretation; hedge causal claims; artworks by
  number only (only Artworks 014/015/016 may be named). Hold the ~60/40
  whitepaper/Ben voice; when quoting source text (prompts, collector profiles) use
  the literal wording, don't paraphrase.
- Data files (`results/**`, `rationales.csv`) are source of truth — the
  frontier→flagship rename must never touch them.

## References
- Reasoning-parity change + comparability caveat: memory `claude-reasoning-parity.md`.
- Original Claude-integration plan (template for this work):
  `~/.claude/plans/can-we-add-a-cheeky-blanket.md`.
- Voice guidance: memory `whitepaper-voice.md`.
