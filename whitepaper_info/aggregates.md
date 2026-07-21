# Precomputed aggregates

All tables exclude error/refusal reviews (error counts are in the first table). Scores are the 0-100 holistic Overall Score; ACQUIRE is the percent of reviews deciding ACQUIRE. Everything here can be recomputed from reviews.csv.

Headline mean overall score per experiment: experiment-1 72.8; experiment-2 65.2; experiment-3 78.0; experiment-4 73.3; experiment-5 54.9; experiment-6 64.0.


## Per experiment × model

| experiment | model | reviews | mean_overall | std_overall | acquire_pct | errors |
|---|---|---|---|---|---|---|
| experiment-1 | gemini-2.5-flash | 396 | 68.6 | 22.6 | 59.3 | 0 |
| experiment-1 | gpt-5-mini | 396 | 77.0 | 12.3 | 70.2 | 0 |
| experiment-2 | gemini-3-flash-preview | 396 | 57.2 | 27.0 | 31.8 | 0 |
| experiment-2 | gpt-5 | 396 | 73.1 | 15.1 | 42.9 | 0 |
| experiment-3 | gemini-2.5-flash | 396 | 75.4 | 17.8 | 71.2 | 0 |
| experiment-3 | gpt-5-mini | 396 | 80.6 | 9.7 | 81.6 | 0 |
| experiment-4 | gemini-3-flash-preview | 396 | 67.3 | 24.7 | 48.5 | 0 |
| experiment-4 | gpt-5 | 396 | 79.3 | 13.0 | 64.9 | 0 |
| experiment-5 | claude-haiku-4-5 | 396 | 55.5 | 23.2 | 27.3 | 0 |
| experiment-5 | claude-sonnet-4-6 | 396 | 54.2 | 28.5 | 40.7 | 0 |
| experiment-6 | claude-haiku-4-5 | 396 | 65.4 | 20.0 | 44.9 | 0 |
| experiment-6 | claude-sonnet-4-6 | 396 | 62.6 | 25.7 | 51.3 | 0 |


## Per experiment × model × condition

| experiment | model | condition | mean_overall | acquire_pct |
|---|---|---|---|---|
| experiment-1 | gemini-2.5-flash | A | 68.3 | 62.1 |
| experiment-1 | gemini-2.5-flash | B | 69.9 | 66.7 |
| experiment-1 | gemini-2.5-flash | C | 72.6 | 71.2 |
| experiment-1 | gemini-2.5-flash | D | 72.9 | 74.2 |
| experiment-1 | gemini-2.5-flash | E · related | 75.1 | 68.2 |
| experiment-1 | gemini-2.5-flash | E · unrelated | 52.6 | 13.6 |
| experiment-1 | gpt-5-mini | A | 77.0 | 77.3 |
| experiment-1 | gpt-5-mini | B | 77.1 | 75.8 |
| experiment-1 | gpt-5-mini | C | 78.9 | 80.3 |
| experiment-1 | gpt-5-mini | D | 79.0 | 87.9 |
| experiment-1 | gpt-5-mini | E · related | 80.3 | 77.3 |
| experiment-1 | gpt-5-mini | E · unrelated | 69.6 | 22.7 |
| experiment-2 | gemini-3-flash-preview | A | 54.9 | 25.8 |
| experiment-2 | gemini-3-flash-preview | B | 52.1 | 24.2 |
| experiment-2 | gemini-3-flash-preview | C | 61.9 | 42.4 |
| experiment-2 | gemini-3-flash-preview | D | 59.3 | 34.8 |
| experiment-2 | gemini-3-flash-preview | E · related | 65.0 | 56.1 |
| experiment-2 | gemini-3-flash-preview | E · unrelated | 50.0 | 7.6 |
| experiment-2 | gpt-5 | A | 73.2 | 42.4 |
| experiment-2 | gpt-5 | B | 73.7 | 47.0 |
| experiment-2 | gpt-5 | C | 77.0 | 57.6 |
| experiment-2 | gpt-5 | D | 76.0 | 56.1 |
| experiment-2 | gpt-5 | E · related | 74.0 | 50.0 |
| experiment-2 | gpt-5 | E · unrelated | 64.8 | 4.5 |
| experiment-3 | gemini-2.5-flash | A | 76.3 | 77.3 |
| experiment-3 | gemini-2.5-flash | B | 79.3 | 86.4 |
| experiment-3 | gemini-2.5-flash | C | 78.8 | 83.3 |
| experiment-3 | gemini-2.5-flash | D | 81.2 | 86.4 |
| experiment-3 | gemini-2.5-flash | E · related | 80.3 | 81.8 |
| experiment-3 | gemini-2.5-flash | E · unrelated | 56.5 | 12.1 |
| experiment-3 | gpt-5-mini | A | 80.1 | 90.9 |
| experiment-3 | gpt-5-mini | B | 80.6 | 90.9 |
| experiment-3 | gpt-5-mini | C | 82.9 | 100.0 |
| experiment-3 | gpt-5-mini | D | 82.6 | 97.0 |
| experiment-3 | gpt-5-mini | E · related | 83.1 | 83.3 |
| experiment-3 | gpt-5-mini | E · unrelated | 74.1 | 27.3 |
| experiment-4 | gemini-3-flash-preview | A | 66.9 | 45.5 |
| experiment-4 | gemini-3-flash-preview | B | 67.5 | 51.5 |
| experiment-4 | gemini-3-flash-preview | C | 73.7 | 65.2 |
| experiment-4 | gemini-3-flash-preview | D | 72.8 | 65.2 |
| experiment-4 | gemini-3-flash-preview | E · related | 70.8 | 59.1 |
| experiment-4 | gemini-3-flash-preview | E · unrelated | 51.8 | 4.5 |
| experiment-4 | gpt-5 | A | 79.5 | 74.2 |
| experiment-4 | gpt-5 | B | 80.5 | 75.8 |
| experiment-4 | gpt-5 | C | 83.6 | 92.4 |
| experiment-4 | gpt-5 | D | 83.1 | 86.4 |
| experiment-4 | gpt-5 | E · related | 80.0 | 57.6 |
| experiment-4 | gpt-5 | E · unrelated | 69.3 | 3.0 |
| experiment-5 | claude-haiku-4-5 | A | 60.6 | 30.3 |
| experiment-5 | claude-haiku-4-5 | B | 54.7 | 25.8 |
| experiment-5 | claude-haiku-4-5 | C | 64.2 | 40.9 |
| experiment-5 | claude-haiku-4-5 | D | 60.5 | 27.3 |
| experiment-5 | claude-haiku-4-5 | E · related | 60.3 | 39.4 |
| experiment-5 | claude-haiku-4-5 | E · unrelated | 33.1 | 0.0 |
| experiment-5 | claude-sonnet-4-6 | A | 52.4 | 42.4 |
| experiment-5 | claude-sonnet-4-6 | B | 53.2 | 34.8 |
| experiment-5 | claude-sonnet-4-6 | C | 62.2 | 53.0 |
| experiment-5 | claude-sonnet-4-6 | D | 61.4 | 54.5 |
| experiment-5 | claude-sonnet-4-6 | E · related | 59.0 | 50.0 |
| experiment-5 | claude-sonnet-4-6 | E · unrelated | 36.9 | 9.1 |
| experiment-6 | claude-haiku-4-5 | A | 69.5 | 48.5 |
| experiment-6 | claude-haiku-4-5 | B | 68.3 | 45.5 |
| experiment-6 | claude-haiku-4-5 | C | 73.8 | 66.7 |
| experiment-6 | claude-haiku-4-5 | D | 71.7 | 57.6 |
| experiment-6 | claude-haiku-4-5 | E · related | 66.1 | 51.5 |
| experiment-6 | claude-haiku-4-5 | E · unrelated | 42.9 | 0.0 |
| experiment-6 | claude-sonnet-4-6 | A | 62.3 | 48.5 |
| experiment-6 | claude-sonnet-4-6 | B | 64.8 | 50.0 |
| experiment-6 | claude-sonnet-4-6 | C | 72.1 | 72.7 |
| experiment-6 | claude-sonnet-4-6 | D | 69.6 | 71.2 |
| experiment-6 | claude-sonnet-4-6 | E · related | 64.2 | 56.1 |
| experiment-6 | claude-sonnet-4-6 | E · unrelated | 42.5 | 9.1 |


## Mean dimension scores (1-10) per experiment × model

| experiment | model | Craft | Composition | Originality | Emotional Resonance | Conceptual Depth |
|---|---|---|---|---|---|---|
| experiment-1 | gemini-2.5-flash | 7.4 | 7.2 | 6.6 | 6.8 | 6.7 |
| experiment-1 | gpt-5-mini | 8.0 | 7.9 | 6.5 | 7.6 | 6.5 |
| experiment-2 | gemini-3-flash-preview | 6.4 | 5.9 | 5.0 | 5.5 | 4.9 |
| experiment-2 | gpt-5 | 7.5 | 7.4 | 6.1 | 7.0 | 6.1 |
| experiment-3 | gemini-2.5-flash | 7.8 | 7.6 | 7.3 | 7.3 | 7.4 |
| experiment-3 | gpt-5-mini | 8.2 | 8.2 | 6.9 | 7.8 | 6.9 |
| experiment-4 | gemini-3-flash-preview | 7.0 | 6.9 | 6.1 | 6.4 | 5.9 |
| experiment-4 | gpt-5 | 8.0 | 8.0 | 7.0 | 7.6 | 6.9 |
| experiment-5 | claude-haiku-4-5 | 7.2 | 6.8 | 5.4 | 6.3 | 5.6 |
| experiment-5 | claude-sonnet-4-6 | 6.8 | 6.6 | 5.6 | 6.4 | 5.5 |
| experiment-6 | claude-haiku-4-5 | 7.6 | 7.4 | 6.3 | 7.1 | 6.6 |
| experiment-6 | claude-sonnet-4-6 | 7.1 | 7.1 | 6.5 | 7.1 | 6.4 |


## Mean overall score per artwork × experiment

| artwork_id | experiment-1 | experiment-2 | experiment-3 | experiment-4 | experiment-5 | experiment-6 |
|---|---|---|---|---|---|---|
| TEST-001 | 74.8 | 72.8 | 78.0 | 78.8 | 62.3 | 71.8 |
| TEST-002 | 71.9 | 53.5 | 80.7 | 70.6 | 36.2 | 53.9 |
| TEST-003 | 72.3 | 59.6 | 81.2 | 74.2 | 51.0 | 63.4 |
| TEST-004 | 81.3 | 83.6 | 83.6 | 83.1 | 71.3 | 76.3 |
| TEST-005 | 68.1 | 69.2 | 77.9 | 78.1 | 53.9 | 64.3 |
| TEST-006 | 74.0 | 66.0 | 77.3 | 75.2 | 54.7 | 65.4 |
| TEST-007 | 49.2 | 38.6 | 64.1 | 56.6 | 28.2 | 39.5 |
| TEST-008 | 76.9 | 61.0 | 82.7 | 76.9 | 41.3 | 60.3 |
| TEST-009 | 81.2 | 69.1 | 83.6 | 81.5 | 65.7 | 74.0 |
| TEST-010 | 82.2 | 71.7 | 82.1 | 78.7 | 54.9 | 64.1 |
| TEST-011 | 81.7 | 81.0 | 86.3 | 85.2 | 70.4 | 79.2 |
| TEST-012 | 78.8 | 75.5 | 80.2 | 80.0 | 62.1 | 66.1 |
| TEST-013 | 74.1 | 68.0 | 77.8 | 77.8 | 66.2 | 71.3 |
| TEST-014 | 94.7 | 97.4 | 92.7 | 97.6 | 94.0 | 96.4 |
| TEST-015 | 93.4 | 96.6 | 90.6 | 94.7 | 86.4 | 87.4 |
| TEST-016 | 93.4 | 94.7 | 90.9 | 93.9 | 90.1 | 92.4 |
| TEST-017 | 53.4 | 37.8 | 69.1 | 48.6 | 25.5 | 34.9 |
| TEST-018 | 55.6 | 41.8 | 64.6 | 52.2 | 24.9 | 36.3 |
| TEST-019 | 50.7 | 43.8 | 60.1 | 48.1 | 46.7 | 54.3 |
| TEST-020 | 48.7 | 35.1 | 57.7 | 43.2 | 34.6 | 41.5 |
| TEST-021 | 69.6 | 58.6 | 75.9 | 68.1 | 39.2 | 52.8 |
| TEST-022 | 75.1 | 58.2 | 78.2 | 69.6 | 47.6 | 62.0 |
