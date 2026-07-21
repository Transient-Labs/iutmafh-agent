# Available figures (screenshots on request)

You (the writing agent) cannot open the interactive dashboards, but the user
can screenshot any chart below and paste it into this conversation. When a
section of the paper needs a figure, ask the user for it **by the exact name
below** (plus the artwork id where applicable). You can also regenerate any
of these yourself from reviews.csv if you have a code-execution tool.

## From the comparison dashboard (dashboards/compare.html)

Series coloring: one hue per experiment; darker shade = the GPT model,
lighter shade = the Gemini model.

- **Experiments summary table** — per experiment × model: reviews, errors,
  mean overall, ACQUIRE rate. (Overview, top.)
- **Mean overall score — condition × experiment · model** — grouped bars,
  A-E on the x-axis, one bar per experiment·model, with run spread.
  (Overview.)
- **ACQUIRE rate — condition × experiment · model** — same layout, percent
  deciding ACQUIRE. (Overview.)
- **Mean overall score — artwork × experiment · model** — 22-row heatmap,
  red-to-green 0-100. (Overview, bottom.)
- **Per-artwork condition bars** — "<artwork_id> — mean overall score by
  condition": the 8 experiment·model series across A-E for one artwork.
  (Pick the artwork in the top strip; name the artwork_id when requesting.)
- **Per-artwork verdict map** — "<artwork_id> — majority verdict per
  condition": green/red/amber grid (ACQUIRE/PASS/split) with mean scores,
  experiment·model rows × condition columns. (Same picker.)

## From the per-experiment dashboards (results/<experiment>/index.html)

Available for each of: experiment-1, experiment-2, experiment-3, experiment-4, experiment-5, experiment-6. One artwork at a time (thumbnail picker):
score-summary heatmap, overall score by condition, per-dimension score
spreads, ACQUIRE/PASS split, run-to-run drift, preference-variant effect,
and a browsable list of every verdict + rationale.

## Requesting a figure

Ask like: "Please screenshot **Mean overall score — condition × experiment ·
model** from the comparison dashboard" or "Please screenshot the
**per-artwork verdict map for TEST-001**." The user will paste the image;
then reference it in the draft as a numbered figure with your caption.
