# AI Art Reviewer Whitepaper — Research Continuation Notes

This document summarizes the current state of the research, paper structure, methodology, conventions, and completed analyses so another ChatGPT session can immediately continue without losing context.

--------------------------------------------------------------------------------
PROJECT OVERVIEW
--------------------------------------------------------------------------------

We are writing a rigorous but readable whitepaper documenting the first large-scale evaluation of production multimodal LLMs acting as autonomous art reviewers.

This research is NOT a product whitepaper.

It is the first published research study supporting the larger Transient Research Division (TRD) art project:

"I Used to Make Art for Humans"

The paper should feel like serious research written for technically literate artists, collectors, creative technologists, and people interested in AI + art.

The paper should NOT read like an academic PhD dissertation, but it also should not read like marketing.

Tone:
- Objective
- Careful
- Honest
- Curious
- Evidence driven
- Accessible

--------------------------------------------------------------------------------
IMPORTANT WRITING RULES
--------------------------------------------------------------------------------

- Never use em dashes.
- Avoid AI cliché sentence structures like:
  "It is not about X. It is about Y."
- Avoid overstating conclusions.
- Observations first.
- Interpretation second.
- Conclusions last.
- Every claim should be directly supported by data.

--------------------------------------------------------------------------------
ANONYMITY REQUIREMENTS
--------------------------------------------------------------------------------

The artwork MUST remain anonymous.

Never describe enough detail for readers to identify the artwork.

Always refer to:

Artwork 001
Artwork 002
...
Artwork 022

The ONLY exceptions are:

Artwork 014
Artwork 015
Artwork 016

These are famous traditional artworks and may be discussed openly.

--------------------------------------------------------------------------------
PURPOSE OF THE STUDY
--------------------------------------------------------------------------------

The goal was NOT to determine whether AI is "good" or "bad" at reviewing art.

The goal was to establish a baseline understanding of how contemporary production multimodal models behave when repeatedly evaluating visual artwork under controlled conditions.

Research questions include:

- How consistent are repeated reviews?
- How much does context influence evaluation?
- Does artist name matter?
- Does artwork description matter?
- Do collector preferences influence acquisition?
- Does reviewer prompt design matter?
- How do economic vs frontier models differ?
- What unexpected behaviors emerge?

This is intentionally exploratory.

--------------------------------------------------------------------------------
THE LARGER ART PROJECT
--------------------------------------------------------------------------------

This research supports:

"I Used to Make Art for Humans"

The project asks:

What happens when the first audience for art is no longer human?

The paper should support this philosophical question through empirical evidence.

The paper should NEVER feel like it exists to sell a future product.

--------------------------------------------------------------------------------
DATASET
--------------------------------------------------------------------------------

22 artworks

Anonymous.

Genres include:

001 Glitch
002 Digital Painting
003 Digital Painting
004 Digital Painting
005 CryptoPunk PFP
006 Glitch Art PFP
007 Generative PFP
008 Photography
009 Photography
010 AI Generated
011 Digital Painting
012 Abstract Digital
013 Glitch
014 Traditional Painting
015 Traditional Painting
016 Photography
017 Generative Art
018 Photography
019 Abstract Physical
020 Physical Drawing
021 Photography
022 Glitch

--------------------------------------------------------------------------------
CONDITIONS
--------------------------------------------------------------------------------

Condition A
Artwork only

Condition B
Artwork + description

Condition C
Artwork + artist name

Condition D
Artwork + description + artist name

Condition E
Artwork + description + artist name + collector preference

Condition E contains:

Related preference

Unrelated preference

--------------------------------------------------------------------------------
MODELS
--------------------------------------------------------------------------------

Economic

GPT-5 Mini

Gemini 2.5 Flash

Frontier

GPT-5

Gemini 3 Flash Preview

--------------------------------------------------------------------------------
PROMPTS
--------------------------------------------------------------------------------

Review Prompt v4

Directive
Highly structured
More reviewer guidance

Review Prompt v5

Minimal
Hands-off
Allows more reviewer discretion

Experiments should NOT be referred to in the paper as "Experiment 1, 2, 3, 4."

Instead use the 2×2 framing:

Prompt v4 + Economic

Prompt v4 + Frontier

Prompt v5 + Economic

Prompt v5 + Frontier

--------------------------------------------------------------------------------
REVIEW STRUCTURE
--------------------------------------------------------------------------------

Each review produced:

First Impression

Interpretation

Five evaluation dimensions

Craft

Composition

Originality

Emotional Resonance

Conceptual Depth

Overall Score

Acquire / Pass

Rationale

--------------------------------------------------------------------------------
REPEATED RUNS
--------------------------------------------------------------------------------

Every identical configuration was evaluated three separate times.

Reviewer consistency is measured from those repeated runs.

--------------------------------------------------------------------------------
SOURCE OF TRUTH
--------------------------------------------------------------------------------

ABSOLUTE RULE:

reviews.csv is the ONLY quantitative source of truth.

Never estimate.

Never rely on memory.

Never reuse previously generated numbers without recomputing from reviews.csv.

Every statistic should be derived directly from reviews.csv.

Dashboards are only for exploration and visualization.

--------------------------------------------------------------------------------
KNOWN DATA ISSUE
--------------------------------------------------------------------------------

One review is marked is_error = True.

Exclude this row from quantitative analysis.

Do not impute or recreate it.

--------------------------------------------------------------------------------
PAPER ROADMAP
--------------------------------------------------------------------------------

1.
Introduction

2.
Research Questions & Study Objectives

3.
Experimental Design

4.
Results

4.1 Reviewer Consistency

4.2 Context Dependence

4.3 Prompt Design

4.4 Model Family Differences

4.5 Emergent Observations

5.
Discussion

6.
Limitations

7.
Future Directions

8.
Abstract

(Abstract written last.)

--------------------------------------------------------------------------------
CURRENT WORKFLOW
--------------------------------------------------------------------------------

We are intentionally NOT writing the Results section yet.

Instead we are creating research notebooks.

Each notebook contains:

Question

Method

Tables

Observations

Follow-up Questions

Interpretation comes later.

--------------------------------------------------------------------------------
REVIEWER CONSISTENCY NOTEBOOK
--------------------------------------------------------------------------------

Question:

How consistently do production multimodal models produce identical acquisition decisions when evaluating identical inputs across repeated runs?

--------------------------------------------------------------------------------
COMPLETED ANALYSIS #1
--------------------------------------------------------------------------------

Computed unanimous decision rate.

Grouped by:

Prompt version

Model tier

Model

Verified directly from reviews.csv.

Results:

Prompt v4

Gemini 2.5 Flash
79.5%

GPT-5 Mini
87.1%

Gemini 3 Flash Preview
86.4%

GPT-5
85.6%

Prompt v5

Gemini 2.5 Flash
84.8%

GPT-5 Mini
89.3%

Gemini 3 Flash Preview
87.9%

GPT-5
90.2%

Observation:

Every model showed higher unanimous decision rates under Prompt v5 than Prompt v4.

Do NOT claim causation.

--------------------------------------------------------------------------------
COMPLETED ANALYSIS #2
--------------------------------------------------------------------------------

Artwork ranking by unanimous decision rate.

Computed directly from reviews.csv.

Lowest consistency:

Artwork 005
64.6%

Artwork 002
77.1%

Artwork 017
77.1%

Artwork 003
81.3%

Artwork 012
81.3%

Artwork 018
81.3%

Artwork 019
81.3%

Artwork 020
81.3%

Highest consistency:

Artwork 004
97.9%

Artwork 015
97.9%

Artwork 016
97.9%

--------------------------------------------------------------------------------
COMPLETED ANALYSIS #3
--------------------------------------------------------------------------------

Broke down the least consistent artworks by model.

Important finding:

Reviewer instability is NOT uniform across models.

Some artworks are unstable for one model but perfectly stable for another.

Example:

Artwork 017

Gemini 2.5 Flash
58.3%

Gemini 3 Flash Preview
100%

Likewise:

Artwork 020

GPT-5 Mini
50%

GPT-5
91.7%

This suggests artwork characteristics and model architecture interact in complex ways.

--------------------------------------------------------------------------------
IMPORTANT INSIGHT
--------------------------------------------------------------------------------

Avoid simplistic conclusions like:

"GPT is more consistent than Gemini."

The data is more nuanced.

Behavior depends on:

Model

Prompt

Artwork

Context

Their interactions are likely more interesting than overall averages.

--------------------------------------------------------------------------------
NEXT STEPS
--------------------------------------------------------------------------------

Continue the Reviewer Consistency notebook.

Investigate WHY the least consistent artworks generated disagreement.

Break instability down by:

- review condition
- prompt version
- model
- score spread
- rationales

Identify behavioral patterns before writing prose.

Only after the notebook is complete should Section 4.1 be drafted.