Introduction
This workbook serves as the experimental record for Chapter 1: Tuning the Agents. Its purpose is to evaluate the baseline behavior of production-oriented multimodal AI models under controlled conditions before developing a standardized review framework in Chapter 2.
Each artwork is evaluated across a series of controlled experimental conditions while varying only one input at a time. By systematically comparing model responses with and without artwork context (description, artist name) and collector preference profiles, this testing seeks to measure consistency, critique quality, context sensitivity, and the ability of each model to produce stable and differentiated aesthetic judgments. Observations recorded throughout this workbook will be used alongside the exported review data to determine whether the models satisfy the success criteria required to proceed to the next phase of the experiment.

How a workbook is run
One workbook = one artwork test run. Artwork facts (image path, title, artist, work type, description, collector preferences) live once per artwork in art_reviewer_sdk/workbooks/artworks.json; the workbook TOML references an entry via `artwork = "<id>"` and carries only the experiment knobs (models, review_prompt, conditions). Fields set directly in the TOML override the catalog, and a TOML without `artwork` still works fully inline. Runs are automated:
    uv run python art_reviewer_sdk/run_workbook.py art_reviewer_sdk/workbooks/workbook.toml
Passing --all sweeps every artwork in the catalog instead: one workbook per artworks.json entry in file order, auto-numbered TEST-001, TEST-002, … (the TOML's artwork/artwork_id keys are ignored; a failed artwork is skipped and re-running --all resumes each results file).
To compare finished experiment runs (results/experiment-*/) against each other — cross-experiment score charts with a per-artwork zoom, and a side-by-side viewer of the per-experiment dashboards — run: uv run python art_reviewer_sdk/compare_dashboards.py --offline --open (writes dashboards/compare.html).
To export the study as an LLM-ready bundle for writing it up (design doc, precomputed stats, per-review CSVs): uv run python art_reviewer_sdk/export_whitepaper.py (writes whitepaper_export/).
The harness (art_reviewer_sdk/run_workbook.py) runs every condition against every model in the TOML's `models` list (falling back to the MODELS default in run_workbook.py — currently gpt-5-mini, gemini-3.5-flash, gemini-3-flash-preview), N runs per condition per model (default 3, --runs to change). All reviews are written incrementally to results/<artwork_id>.json with a flat .summary.json beside it; interrupted runs resume. The system prompt is selected by review_prompt = <N> in the TOML (review_prompt_<N>.py) and recorded with the results. Sampling knobs and the image downscale cap are also recorded in the results JSON.
The condition is decided purely by which inputs the harness sends; it is experiment metadata and is never injected into the prompt.

Experimental Conditions
Condition A — Artwork Only
    No description, no artist name, no collector preference.
Condition B — Artwork + Description
    The submitter-provided description is added to the user message.
Condition C — Artwork + Artist Name
    The artist's name is added; no description.
Condition D — Artwork + Description + Artist Name
Condition E — Artwork + Description + Artist Name + Collector Preference
    Run once per named entry in the [preferences] table (e.g. related /
    unrelated); each pass is recorded with its preference_variant.
    A preference value ending in .json is a path to a collector taste-profile
    file (kept in art_reviewer_sdk/workbooks/collector-preferences/), resolved relative to
    whichever file defined it (artworks.json or the TOML). A string profile is
    sent verbatim; an object profile is filtered to the taste fields
    (preferredMediums, priorityRanking, collectorStatement,
    favoriteArtistsOrWorks, avoid — identity fields like collectorName are
    never sent) and serialized. The text actually sent and the source path are
    both recorded in the results. Plain inline strings still work.
All conditions also send the artwork's listed price, maximum spend, work type, and media note (e.g. "the artwork is animated; the image provided is a static screenshot") when present in the TOML or catalog entry.

A–E is only the default structure. A workbook TOML can define its own [[conditions]] tables — each with a key, a label, and a `send` list choosing which inputs go to the model (description, artist, preferences, price, max_spend, work_type) — so other experiment designs (e.g. isolating price as the varied input, see art_reviewer_sdk/workbooks/workbook_pricing.toml) run through the same harness. Each condition's send list and actual input values are recorded in the results JSON, and the dashboard renders whatever structure the file describes.

Observation Guide
Consistency: Does the model reach similar conclusions when evaluating the same artwork multiple times?
Review Drift: Does the critique remain directionally similar across repeated evaluations, or does it significantly change over time?
Context Sensitivity: Does the model respond appropriately when new context is added, such as an artwork description or artist name?
Taste Adaptation: Does the model adjust its judgment based on the collector preference provided (Condition E), without preference alone deterministically deciding the outcome?
Critique Quality: Does the review provide thoughtful artistic evaluation rather than simply describing the image?
Reasoning Coherence: Does the written critique logically support the model's final decision?
Decision Balance: Does the model produce a healthy mix of approvals and rejections across the testing dataset?

Chapter 1 Testing Workbook
Complete one observation record for each artwork evaluated. (Raw scores and
decisions live in results/<artwork_id>.json; record qualitative observations here.)

Artwork Information
Artwork ID: ____________________________
Artwork Title: __________________________
Artist: ________________________________
Work Type:
Digitally native (NFT / digital asset)
Digital representation of a physical work
Artwork Type:
Representational
Abstract
Conceptual
Technical
Ambiguous
Review Prompt Version: __________________
Models / Runs per condition: _____________
Date: ____________________________
Researcher: _____________________

Observations — Condition A (Artwork Only)
____________________________________________________________
____________________________________________________________

Observations — Condition B (+ Description)
____________________________________________________________
____________________________________________________________

Observations — Condition C (+ Artist Name)
____________________________________________________________
____________________________________________________________

Observations — Condition D (+ Description + Artist Name)
____________________________________________________________
____________________________________________________________

Observations — Condition E (+ Collector Preference, per variant)
____________________________________________________________
____________________________________________________________

Cross-Condition Observations
Consistency:
____________________________________________________________
____________________________________________________________
Review Drift:
____________________________________________________________
____________________________________________________________
Context Sensitivity:
____________________________________________________________
____________________________________________________________
Taste Adaptation:
____________________________________________________________
____________________________________________________________
Decision Balance:
____________________________________________________________
____________________________________________________________
Critique Quality:
____________________________________________________________
____________________________________________________________
Reasoning Coherence:
____________________________________________________________
____________________________________________________________
Notes:
____________________________________________________________
____________________________________________________________

Overall Artwork Summary
Consistency acceptable
Taste differentiation observed
Critiques demonstrate interpretation
Reasoning supports decisions
Approval/rejection distribution appears balanced

Overall Assessment:
Proceed 
Needs Revision
Retest

Summary:
____________________________________________________________
____________________________________________________________
____________________________________________________________
