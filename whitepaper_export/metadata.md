# Study design

## Experiments

The study is a 2×2 design: model set × system-prompt version. Every experiment reviewed the same artworks under the same conditions.

| experiment | models | system prompt | runs/condition | sampling knobs | max image edge | started |
|---|---|---|---|---|---|---|
| experiment-1 | gpt-5-mini + gemini-2.5-flash | v4 | 3 | {} | 1024 | 2026-07-10 |
| experiment-2 | gpt-5 + gemini-3-flash-preview | v4 | 3 | {} | 1024 | 2026-07-14 |
| experiment-3 | gpt-5-mini + gemini-2.5-flash | v5 | 3 | {} | 1024 | 2026-07-15 |
| experiment-4 | gpt-5 + gemini-3-flash-preview | v5 | 3 | {} | 1024 | 2026-07-15 |
| experiment-5 | claude-sonnet-4-6 + claude-sonnet-5 | v4 | 3 | {} | 1024 | 2026-07-22 |
| experiment-6 | claude-sonnet-4-6 + claude-sonnet-5 | v5 | 3 | {} | 1024 | 2026-07-24 |


## Experimental conditions

The condition determines which inputs are sent with the artwork image; it is never named in the prompt itself. Conditions that send `preferences` run once per collector-preference variant.

| condition | label | inputs sent | preference variants |
|---|---|---|---|
| A | Artwork Only | price, max_spend, work_type, media_note | — |
| B | Artwork + Description | description, price, max_spend, work_type, media_note | — |
| C | Artwork + Artist Name | artist, price, max_spend, work_type, media_note | — |
| D | Artwork + Description + Artist Name | description, artist, price, max_spend, work_type, media_note | — |
| E | Artwork + Description + Artist Name + Collector Preference | description, artist, preferences, price, max_spend, work_type, media_note | related, unrelated |


## Collector-preference profiles

Sent verbatim (as JSON) in conditions that include `preferences`. `related` aligns with the tested art; `unrelated` does not.


### Variant: related

```
{
  "preferredMediums": [
    "Glitch Art",
    "Databending / Corruption Aesthetics",
    "Experimental Digital"
  ],
  "priorityRanking": {
    "originality": 1,
    "innovation": 2,
    "technicalExecution": 3,
    "conceptOrMeaning": 4,
    "colorAndAesthetics": 5,
    "composition": 6,
    "emotionalImpact": 7,
    "historicalSignificance": 8,
    "collectability": 9
  },
  "collectorStatement": "I'm fascinated by work that embraces digital failure as a material — databending, compression artifacts, corrupted signals, broken renderers, and misused tools. I gravitate toward artists who push systems until they break interestingly and find real beauty and meaning inside distortion, noise, and error.",
  "favoriteArtistsOrWorks": [
    "XCOPY",
    "Rosa Menkman",
    "JODI",
    "Sarah Zucker",
    "Domenico Barra"
  ],
  "avoid": "Overly polished commercial aesthetics, off-the-shelf glitch filters, generic AI imagery, and work that wears experimentation as a surface style."
}
```

### Variant: unrelated

```
{
  "preferredMediums": [
    "Photography",
    "Fine Art Photography",
    "Documentary / Street Photography"
  ],
  "priorityRanking": {
    "composition": 1,
    "emotionalImpact": 2,
    "originality": 3,
    "technicalExecution": 4,
    "conceptOrMeaning": 5,
    "colorAndAesthetics": 6,
    "historicalSignificance": 7,
    "innovation": 8,
    "collectability": 9
  },
  "collectorStatement": "I'm drawn to photography that rewards slow looking — patient light, decisive timing, honest color, and a strong sense of place. I care about what was actually in front of the lens and the photographer's judgment in that moment, more than technical perfection or dramatic post-processing.",
  "favoriteArtistsOrWorks": [
    "Todd Hido",
    "Hiroshi Sugimoto",
    "Michael Kenna",
    "Gregory Crewdson",
    "Fan Ho"
  ],
  "avoid": "Overprocessed edits, cliché travel imagery, excessive HDR, and heavily composited scenes that abandon the truth of the photographic moment."
}
```


## System prompts

The full reviewer system prompt used by each experiment (the v4 → v5 change is one of the two study factors).


### Prompt v4 (used by experiment-1, experiment-2, experiment-5)

```
You are an art reviewer: an autonomous agent with a developed, coherent
aesthetic sensibility. You review artworks and decide whether to acquire
them. The taste is yours and the verdict is yours. When the collector you
curate for states preferences, weigh them; when none are given, your own
judgment is the only standard — there is no other audience to satisfy.

When you are shown an image of an artwork, review it by calling the
`submit_review` tool. Fill every field of the structured review:

- **First Impression** — 2-3 sentences of immediate, honest reaction
  before any analysis.
- **Interpretation** — what this work is doing or attempting. Read it:
  subject, formal choices (composition, color, mark-making, material),
  and what they add up to. Interpret, do not merely describe.
- **Evaluation** — assess the work across five dimensions. For each,
  give an integer Score from 1-10 and one or two sentences of Reasoning:
  - **Craft** — command of medium and technique
  - **Composition** — structural and formal strength
  - **Originality** — does it offer something not already abundant
  - **Emotional Resonance** — does it produce a felt response
  - **Conceptual Depth** — is there something to return to
- **Verdict**:
  - **Overall Score** — an integer 0-100, your holistic judgment, NOT an
    average of the dimension scores.
  - **Decision** — ACQUIRE or PASS.
  - **Rational** — 2-3 sentences. Take a position; do not hedge.

Rules:
- You have taste. Express genuine preference, not neutral summary.
- Be willing to reject work. Acquisition is an endorsement, not a participation
  award.
- Never inflate scores out of politeness. A 5 is average, an 8 is rare,
  a 10 is once-in-a-career.
- Argue from what the work does, never from imagined buyers. Do not justify
  a decision by appeal to a hypothetical collector, collection, audience, or
  market ("would suit a collector who…", "for a collection focused on…").
  If no preferences were provided, do not invent or assume any.

```

### Prompt v5 (used by experiment-3, experiment-4, experiment-6)

```
You review artworks for acquisition by a human art collector. If collector
preferences are provided, take them into account.

When you are shown an image of an artwork, review it by calling the
`submit_review` tool. Fill every field of the structured review:

- **First Impression**
- **Interpretation**
- **Evaluation** — for each of the five dimensions (Craft, Composition,
  Originality, Emotional Resonance, Conceptual Depth), an integer Score
  from 1-10 and brief Reasoning.
- **Verdict**:
  - **Overall Score** — an integer 0-100.
  - **Decision** — ACQUIRE or PASS.
  - **Rational** — brief explanation.

```


## Artwork catalog

| artwork_id | title | artist | work type | media note |
|---|---|---|---|---|
| TEST-001 | Proof of War | xcopy | — | The artwork is animated; the image provided is a static screenshot/rendition of the work. |
| TEST-002 | Into the Ether #117/207 | Beeple | — | — |
| TEST-003 | January First, 2021 | Beeple | — | — |
| TEST-004 | Singular Focus | Sam Spratt | — | — |
| TEST-005 | CryptoPunk #8340 | Larva Labs | — | — |
| TEST-006 | Grifter #583 | xcopy | — | — |
| TEST-007 | Bored Ape Yatch Club #2730 | Yuga Labs | — | — |
| TEST-008 | Lux No. 1 | Ben Strauss | — | — |
| TEST-009 | Clocked | Paul Seibert | — | — |
| TEST-010 | sign left on | 0009 | — | — |
| TEST-011 | The Gatehouse | Paul Reid | — | — |
| TEST-012 | Violet for Transmutation | Crow | — | — |
| TEST-013 | If You Come For The King | m0dest | — | The artwork is animated; the image provided is a static screenshot/rendition of the work. |
| TEST-014 | Saturn Devouring His Son | Francisco Goya | — | — |
| TEST-015 | Judith Beheading Holofernes | Caravaggio | — | — |
| TEST-016 | Migrant Mother | Dorothea Lange | — | — |
| TEST-017 | Sticks and Stones | Elara Vance | — | — |
| TEST-018 | Tundra | Bear Otto | — | — |
| TEST-019 | Seeing | Bear Otto | — | — |
| TEST-020 | Sparkles | Bear Otto | — | — |
| TEST-021 | Steel | DJKERO | — | — |
| TEST-022 | The Volunteer | Nawhsan | — | — |
