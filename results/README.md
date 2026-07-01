# Results

One JSON per workbook run (`run_workbook.py`), plus a flat `.summary.json`
beside each.

**Comparability break (2026-07-01):** everything in `archive/` was produced
before two changes to `art_reviewer_sdk/review.py`:

1. The `submit_review` tool schema previously embedded rubric language in its
   field descriptions ("Roughly half of competent works should still be PASS",
   "(5 average, 8 rare, 10 once-in-a-career)", "Take a position; do not
   hedge") on every run, regardless of the selected `review_prompt_<N>`. The
   schema is now instruction-neutral so the system prompt is the only
   instruction source.
2. The collector-preference framing in the user message changed from
   "Collector preferences to weigh in your judgment" to preferences-as-
   tendencies ("not rules — exceptional work outside them can still merit
   acquisition").

Do not compare archived scores/decisions directly against runs produced after
this date. Results JSONs now also record `sampling_knobs` and
`max_image_edge` in the `workbook` block.
