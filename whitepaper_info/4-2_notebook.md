# 4.2 Context Dependence Research Notebook

**RQ2 / Goal:** Determine how additional contextual information (descriptions, artist names, collector preferences) influences reviewer scores and acquisition decisions.

## Method

Each artwork was reviewed under six context settings: A (artwork only), B (+ description), C (+ artist name), D (+ description + artist name), and E split into two collector profiles, E-related (a collector whose stated taste matches the work's genre) and E-unrelated (a mismatched collector). The seven collector profiles are genre-based (abstract, ai, generative, glitch, painting, pfp, photography); "related" is the matching profile, "unrelated" a deliberately mismatched one.

All quantitative values are recomputed from reviews.csv, errors excluded. For paired effects, each cell is one configuration's mean over its three runs (per prompt, artwork, model, context); a signal's effect is the average change within the same artwork, model, and prompt when only that one input is added, so the artwork and model are held fixed. Rationale quotes are pulled verbatim from the full review data to show mechanism, not to generate numbers.

## Analysis 1 — Headline: score and acquisition by context

Pooled across all models and both prompts.

| Context | Mean overall | ACQUIRE rate |
|---|---:|---:|
| A · artwork only | 72.0 | 61.9% |
| B · + description | 72.6 | 64.8% |
| C · + artist name | 76.2 | 74.1% |
| D · + description + artist | 75.9 | 73.5% |
| E · related collector | 76.1 | 66.7% |
| E · unrelated collector | 61.1 | 11.9% |

## Analysis 2 — Isolating each signal (paired, holds artwork + model + prompt fixed)

| Change | Score effect | ACQUIRE effect |
|---|---:|---:|
| Add description (B − A) | +0.6 | +2.8 |
| Add description on top of artist (D − C) | −0.3 | −0.6 |
| Add artist name (C − A) | +4.1 | +12.1 |
| Add artist name on top of description (D − B) | +3.3 | +8.7 |
| Add related collector (E-related − D) | +0.2 | −6.8 |
| Add unrelated collector (E-unrelated − D) | −14.8 | −61.6 |
| Related vs unrelated collector | +15.0 | +54.7 |

Effects are in points (score on the 0 to 100 scale; ACQUIRE in percentage points). n = 176 paired configurations per row.

## Analysis 2b — Description is flat on average but not artwork by artwork

The near-zero description average hides real artwork-level movement. Across all artwork and model cells, the description score effect (B − A) has a mean of only +0.6 but a standard deviation of 6.2 and a range from −24 to +25, and 26% of cells move by 5 points or more. The gains concentrate on works that do not explain themselves visually (abstract, generative, and similar), on the two Gemini models, and on cells where the artwork-only baseline was low, so the description is rescuing a work the image alone left the model uncertain about.

Examples of the description effect (B − A), pooled across prompts:

| Artwork | Model | A score | B score | Score effect | ACQUIRE effect |
|---|---|---:|---:|---:|---:|
| 002 (digital painting) | Gemini 3 Flash Preview | 36.0 | 61.5 | +25.5 | +33.3 |
| 005 (PFP) | Gemini 2.5 Flash | 48.3 | 69.2 | +20.8 | +50.0 |
| 017 (generative) | Gemini 2.5 Flash | 41.2 | 52.2 | +11.0 | +50.0 |
| 017 (generative) | Gemini 3 Flash Preview | 18.3 | 26.2 | +7.8 | 0.0 |
| 008 | Gemini 2.5 Flash | 70.8 | 75.5 | +4.7 | +33.3 |

For the same works, GPT-5 and GPT-5 Mini barely moved, and for works that read clearly on their own the description did little for any model.

## Analysis 3 — Collector preference is the dominant signal

By model, E-related vs E-unrelated:

| Model | Related score | Related ACQUIRE | Unrelated score | Unrelated ACQUIRE |
|---|---:|---:|---:|---:|
| Gemini 2.5 Flash | 77.7 | 75.0% | 54.6 | 12.9% |
| Gemini 3 Flash Preview | 67.9 | 57.6% | 50.9 | 6.1% |
| GPT-5 | 77.0 | 53.8% | 67.0 | 3.8% |
| GPT-5 Mini | 81.7 | 80.3% | 71.8 | 25.0% |

Unrelated-collector effect vs the D baseline (paired), ACQUIRE points: Gemini 2.5 Flash −67.4, GPT-5 −67.4, GPT-5 Mini −67.4, Gemini 3 Flash Preview −43.9. Every model collapses; three of four fall by about 67 points.

Mechanism, from the review rationales under an unrelated collector (verbatim):
- "Despite the high technical quality, the work is a digital painting and lacks the algorithmic/generative system central to the collector's preferences." (Artwork 004)
- "The work is a total departure from the requested photography medium. It lacks the patient, naturalistic qualities the collector values." (Artwork 006)
- "The piece does not align with the collector's focus on PFP and character sets." (Artwork 010)

The models stop judging the work on its own terms and judge its fit to the stated collector. A related collector barely moves the score (+0.2) yet still lowers acquisition (−6.8 pooled), so even an aligned preference makes reviewers more selective. Related-collector ACQUIRE effect splits by model: GPT-5 −17.4, GPT-5 Mini −12.1, Gemini 2.5 Flash −5.3, Gemini 3 Flash Preview +7.6.

## Analysis 4 — Artist name helps, but not where you would guess

Artist-name effect (C − A) by model:

| Model | Score | ACQUIRE |
|---|---:|---:|
| Gemini 3 Flash Preview | +6.8 | +18.2 |
| GPT-5 | +3.9 | +16.7 |
| Gemini 2.5 Flash | +3.3 | +7.6 |
| GPT-5 Mini | +2.4 | +6.1 |

Split by whether the artist is one of the three canonical (famous) works vs the rest:

| Group | Baseline A score | Artist-name score effect | Artist-name ACQUIRE effect |
|---|---:|---:|---:|
| Canonical (014, 015, 016) | 95.4 | +0.4 | +0.0 |
| All other artworks | 68.3 | +4.7 | +14.0 |

The canonical works gain nothing from the artist name. The most likely reason is a ceiling: they already score 95.4 from the image alone, leaving no room to rise. The lift from a name lands on the unknown contemporary works, where the name is new information.

## Observations

- Adding a description alone did little on average, but this hides real artwork-level variation. For works that do not read clearly on their own, mostly abstract and generative pieces reviewed by the Gemini models, a description raised the score and acquisition substantially (for example Artwork 017 with Gemini 2.5 Flash, +11 score and +50 acquisition points). When the image already communicated, the description added almost nothing.
- Naming the artist was the one context signal in the A to D range that clearly moved both score and acquisition, and it was redundant with the description once present.
- The collector preference dominated everything else. A mismatched collector cut acquisition by roughly 62 points and the score by about 15, a far larger swing than any other signal.
- A matched collector left the score essentially unchanged but still reduced acquisition, so the preference gate makes reviewers more conservative even when the taste aligns.
- Every model collapsed under the mismatched collector, though by different amounts. Gemini 2.5 Flash fell the hardest on score; Gemini 3 Flash Preview retained the most acquisitions.
- The artist-name lift was absent for the three canonical works, consistent with a scoring ceiling rather than indifference to the name.

## Follow-up questions

- Description matters for visually ambiguous works (Analysis 2b). Open question: is the trigger the artwork's genre, its artwork-only baseline score, or the length and specificity of the description text itself? Worth correlating the description effect against baseline score and description length.
- Is the related-collector acquisition drop a real "more selective" effect, or an artifact of the acquisition threshold shifting? The rationales under E-related would tell us.
- For the unrelated collapse, do models ever acquire against the stated preference, and what do those rationales say?
- Does context change the five dimension scores differently (for example, does artist name lift Originality or Conceptual Depth more than Craft)?

## Proposed section structure and figures

1. **Score and acquisition by context** (Figure): the six-bar A to E-unrelated progression, score and acquisition side by side. The headline picture.
2. **Isolating the signals** (Table 2 above): description near zero, artist name positive, preference dominant.
3. **The collector-preference effect** (Figure + rationale quotes): related vs unrelated, most likely reusing your per-artwork across-conditions line chart with an artwork where the unrelated cliff is sharp. This is the emotional center of the section.
4. **Artist name and the ceiling** (small table): the canonical-vs-other contrast.
