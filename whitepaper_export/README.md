# Art-reviewer study — data bundle

Generated 2026-07-20T16:02:00-06:00 from
results/experiment-*/. An autonomous "art reviewer" agent (an LLM given a
structured review rubric) reviewed 22 artworks and
decided ACQUIRE or PASS for each. The study varies two factors (2×2):
the model set and the system-prompt version (v4 = directive, with taste/
scoring rules; v5 = minimal, structure only):

- experiment-1 — gpt-5-mini + gemini-2.5-flash · v4
- experiment-2 — gpt-5 + gemini-3-flash-preview · v4
- experiment-3 — gpt-5-mini + gemini-2.5-flash · v5
- experiment-4 — gpt-5 + gemini-3-flash-preview · v5
- experiment-5 — claude-haiku-4-5 + claude-sonnet-4-6 · v4
- experiment-6 — claude-haiku-4-5 + claude-sonnet-4-6 · v5

Each artwork was reviewed under every experimental condition (A-E: which
contextual inputs accompany the image — see metadata.md), 3 runs per
condition per model. Total reviews: 4752.

## Files

- **metadata.md** — study design: experiments, condition definitions, the
  full system-prompt texts, collector-preference profiles, artwork catalog.
- **aggregates.md** — precomputed stats tables (recomputable from reviews.csv).
- **reviews.csv** — one row per review (4752 rows), numeric only:
  dimension scores (1-10), overall score (0-100), decision.
- **rationales.csv** — the model's 2-3 sentence verdict rationale for every
  review (for qualitative quotes).
- **figures.md** — the charts the user can screenshot for you on request;
  ask for them by name when the paper needs a figure.

Rows across the CSVs key on (experiment, artwork_id, condition,
preference_variant, model, run). `preference_variant` is empty except in
conditions that send collector preferences. `is_error` marks refusals or
malformed reviews — exclude them from numeric analysis.
