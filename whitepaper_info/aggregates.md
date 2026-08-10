# Precomputed aggregates

All tables exclude error/refusal reviews (error counts are in the first table). Scores are the 0-100 holistic Overall Score; ACQUIRE is the percent of reviews deciding ACQUIRE. Everything here can be recomputed from reviews.csv.

Headline mean overall score per experiment: experiment-1 72.8; experiment-2 65.2; experiment-3 78.0; experiment-4 73.3; experiment-5 47.6; experiment-6 55.9.


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
| experiment-5 | claude-sonnet-4-6 | 396 | 50.9 | 28.6 | 30.8 | 0 |
| experiment-5 | claude-sonnet-5 | 396 | 44.3 | 23.6 | 14.9 | 0 |
| experiment-6 | claude-sonnet-4-6 | 396 | 60.6 | 26.4 | 46.5 | 0 |
| experiment-6 | claude-sonnet-5 | 396 | 51.2 | 23.6 | 21.7 | 0 |


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
| experiment-5 | claude-sonnet-4-6 | A | 48.0 | 28.8 |
| experiment-5 | claude-sonnet-4-6 | B | 49.6 | 27.3 |
| experiment-5 | claude-sonnet-4-6 | C | 57.4 | 42.4 |
| experiment-5 | claude-sonnet-4-6 | D | 56.8 | 40.9 |
| experiment-5 | claude-sonnet-4-6 | E · related | 55.6 | 43.9 |
| experiment-5 | claude-sonnet-4-6 | E · unrelated | 38.1 | 1.5 |
| experiment-5 | claude-sonnet-5 | A | 44.0 | 13.6 |
| experiment-5 | claude-sonnet-5 | B | 42.8 | 13.6 |
| experiment-5 | claude-sonnet-5 | C | 46.5 | 15.2 |
| experiment-5 | claude-sonnet-5 | D | 46.3 | 13.6 |
| experiment-5 | claude-sonnet-5 | E · related | 50.9 | 33.3 |
| experiment-5 | claude-sonnet-5 | E · unrelated | 35.0 | 0.0 |
| experiment-6 | claude-sonnet-4-6 | A | 60.3 | 43.9 |
| experiment-6 | claude-sonnet-4-6 | B | 61.1 | 45.5 |
| experiment-6 | claude-sonnet-4-6 | C | 68.6 | 63.6 |
| experiment-6 | claude-sonnet-4-6 | D | 68.4 | 69.7 |
| experiment-6 | claude-sonnet-4-6 | E · related | 62.0 | 53.0 |
| experiment-6 | claude-sonnet-4-6 | E · unrelated | 43.0 | 3.0 |
| experiment-6 | claude-sonnet-5 | A | 51.5 | 21.2 |
| experiment-6 | claude-sonnet-5 | B | 51.1 | 19.7 |
| experiment-6 | claude-sonnet-5 | C | 56.3 | 25.8 |
| experiment-6 | claude-sonnet-5 | D | 55.2 | 24.2 |
| experiment-6 | claude-sonnet-5 | E · related | 54.6 | 39.4 |
| experiment-6 | claude-sonnet-5 | E · unrelated | 38.7 | 0.0 |


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
| experiment-5 | claude-sonnet-4-6 | 6.5 | 6.3 | 5.1 | 6.0 | 5.1 |
| experiment-5 | claude-sonnet-5 | 5.8 | 6.0 | 4.0 | 4.9 | 3.9 |
| experiment-6 | claude-sonnet-4-6 | 6.9 | 6.9 | 6.1 | 6.9 | 6.2 |
| experiment-6 | claude-sonnet-5 | 6.2 | 6.5 | 4.7 | 5.5 | 4.6 |


## Mean overall score per artwork × experiment

| artwork_id | experiment-1 | experiment-2 | experiment-3 | experiment-4 | experiment-5 | experiment-6 |
|---|---|---|---|---|---|---|
| TEST-001 | 74.8 | 72.8 | 78.0 | 78.8 | 51.8 | 61.7 |
| TEST-002 | 71.9 | 53.5 | 80.7 | 70.6 | 27.2 | 40.4 |
| TEST-003 | 72.3 | 59.6 | 81.2 | 74.2 | 39.2 | 52.2 |
| TEST-004 | 81.3 | 83.6 | 83.6 | 83.1 | 64.6 | 74.1 |
| TEST-005 | 68.1 | 69.2 | 77.9 | 78.1 | 43.2 | 55.4 |
| TEST-006 | 74.0 | 66.0 | 77.3 | 75.2 | 49.7 | 60.5 |
| TEST-007 | 49.2 | 38.6 | 64.1 | 56.6 | 29.9 | 38.2 |
| TEST-008 | 76.9 | 61.0 | 82.7 | 76.9 | 36.1 | 49.7 |
| TEST-009 | 81.2 | 69.1 | 83.6 | 81.5 | 55.5 | 68.8 |
| TEST-010 | 82.2 | 71.7 | 82.1 | 78.7 | 46.5 | 56.1 |
| TEST-011 | 81.7 | 81.0 | 86.3 | 85.2 | 71.0 | 79.3 |
| TEST-012 | 78.8 | 75.5 | 80.2 | 80.0 | 45.4 | 53.8 |
| TEST-013 | 74.1 | 68.0 | 77.8 | 77.8 | 47.9 | 55.7 |
| TEST-014 | 94.7 | 97.4 | 92.7 | 97.6 | 97.7 | 98.0 |
| TEST-015 | 93.4 | 96.6 | 90.6 | 94.7 | 90.5 | 92.0 |
| TEST-016 | 93.4 | 94.7 | 90.9 | 93.9 | 93.5 | 93.0 |
| TEST-017 | 53.4 | 37.8 | 69.1 | 48.6 | 18.5 | 23.1 |
| TEST-018 | 55.6 | 41.8 | 64.6 | 52.2 | 17.3 | 21.0 |
| TEST-019 | 50.7 | 43.8 | 60.1 | 48.1 | 28.7 | 35.3 |
| TEST-020 | 48.7 | 35.1 | 57.7 | 43.2 | 22.5 | 26.4 |
| TEST-021 | 69.6 | 58.6 | 75.9 | 68.1 | 34.2 | 43.3 |
| TEST-022 | 75.1 | 58.2 | 78.2 | 69.6 | 35.8 | 52.3 |
