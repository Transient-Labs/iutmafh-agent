# iutmafh-agent

Artwork review agents for **"I Used To Make Art For Humans"** — an
experiment in agentic art selection by Transient Labs. See `RESEARCH.md`
for the full experiment outline. We are currently in **Chapter 1: Tuning
the Agents** — benchmarking aesthetic judgment across Gemini, Claude, and
OpenAI models.

## Layout

| Path | What it is |
|---|---|
| `art_reviewer_sdk/review.py` | Thin build: one script, official SDKs, no framework |
| `art_reviewer_adk/` | Google ADK build (dev web UI via `uv run adk web`) |
| `review_prompt.py` | The shared reviewer system prompt — single source of truth |

## Usage (direct build)

```bash
uv run python art_reviewer_sdk/review.py path/to/artwork.jpg
uv run python art_reviewer_sdk/review.py artwork.jpg --model gpt-5.1
```

The model is chosen by `--model`, falling back to `ART_REVIEWER_MODEL` in
`.env`. Routing is by ID prefix: `gemini-*` → google-genai SDK,
`claude-*` → anthropic SDK, anything else → openai SDK.

Knobs (all optional, set in `.env`): `ART_REVIEWER_TEMPERATURE`,
`ART_REVIEWER_TOP_P`, `ART_REVIEWER_MAX_TOKENS`. Sampling knobs are
auto-skipped for models that reject them (Claude 4.7+/Fable, OpenAI
gpt-5/o-series).

## Web UI (direct build)

`art_reviewer_sdk/server.py` serves a one-page upload UI on top of the
same `review_image()` the CLI uses. Run it from the repo root:

```bash
uv run uvicorn art_reviewer_sdk.server:app --port 8000
```

Then open <http://localhost:8000>. Add `--reload` for auto-restart on
code changes during development.

To stop it: press `Ctrl+C` in the terminal running it. If it's
backgrounded or you lost the terminal, kill it by port:

```bash
lsof -ti:8000 | xargs kill        # add -9 if it won't exit
```

## Available models

Vision-capable chat models relevant to art review. Gemini and OpenAI
lists were queried live from this project's API keys on 2026-06-12;
re-check anytime with the snippet below each provider.

### Gemini (verified against our key)

| Model | Notes |
|---|---|
| `gemini-3.1-pro-preview` | Newest pro tier (preview) |
| `gemini-3-pro-preview` | Pro tier (preview) |
| `gemini-3.5-flash` | Newest flash |
| `gemini-3-flash-preview` | |
| `gemini-2.5-pro` | Stable pro — strong default for judgment quality |
| `gemini-2.5-flash` | Stable flash — current project default |
| `gemini-2.5-flash-lite` | Cheapest |
| `gemini-2.0-flash` / `-lite` | Older generation |
| `gemini-pro-latest` / `gemini-flash-latest` | Floating aliases (track newest stable) |

Re-query: `client.models.list()` filtered to `generateContent` support.

### OpenAI (verified against our key)

| Model | Notes |
|---|---|
| `gpt-5.5` / `gpt-5.5-pro` | Newest flagship / pro |
| `gpt-5.4` / `-mini` / `-nano` / `-pro` | |
| `gpt-5.2` / `gpt-5.2-pro` | |
| `gpt-5.1` | |
| `gpt-5` / `-mini` / `-nano` / `-pro` | |
| `gpt-4.1` / `-mini` / `-nano` | Non-reasoning generation |
| `gpt-4o` / `gpt-4o-mini` | Older multimodal workhorses |
| `o3`, `o4-mini`, `o1` | Reasoning series (no sampling params) |

(Account also has image/audio/realtime/embedding models — not relevant
for reviews.) Re-query: `OpenAI().models.list()`.

### Claude (not yet verified — `ANTHROPIC_API_KEY` is empty)

Current lineup per Anthropic docs; verify with
`anthropic.Anthropic().models.list()` once a key is added.

| Model | Notes |
|---|---|
| `claude-opus-4-8` | Most capable Opus tier — recommended default |
| `claude-fable-5` | Most capable overall; premium pricing; no sampling params |
| `claude-opus-4-7` / `claude-opus-4-6` | Previous Opus generations |
| `claude-sonnet-4-6` | Speed/cost balance |
| `claude-haiku-4-5` | Fastest/cheapest |

Use exact IDs as written — no date suffixes (e.g. never
`claude-sonnet-4-6-20251114`). Claude 4.7+, Fable, and OpenAI's
gpt-5/o-series reject `temperature`/`top_p`; the script handles this
automatically.

## Setup

```bash
uv sync                      # installs everything from uv.lock
```

`.env` keys (gitignored — never commit): `GEMINI_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.
