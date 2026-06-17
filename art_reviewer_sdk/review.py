#!/usr/bin/env python3
"""Direct art reviewer — no agent framework, one SDK call per review.

Sends an artwork image to Gemini, Claude, or OpenAI using each
provider's official SDK, selected by ART_REVIEWER_MODEL (or --model).

Usage:
    uv run python art_reviewer_sdk/review.py path/to/artwork.jpg
    uv run python art_reviewer_sdk/review.py artwork.jpg --model claude-opus-4-8

Model IDs are plain provider IDs (no prefix needed):
    gemini-2.5-flash, gemini-2.5-pro
    claude-opus-4-8, claude-sonnet-4-6
    gpt-5.1, gpt-4o
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from review_prompt import INSTRUCTION

DEFAULT_MODEL = "gemini-2.5-flash"
USER_PROMPT = "Review this artwork."


# The review is returned as structured tool input following this schema —
# keys and nesting match json-template.json exactly so the web UI can render
# and store them directly. Descriptions mirror the rubric in review_prompt.py.
REVIEW_TOOL_NAME = "submit_review"
REVIEW_TOOL_DESCRIPTION = (
    "Submit the structured art review, following the reviewer rubric. Score "
    "fields are integers; Reasoning/prose fields are plain sentences."
)

# Evaluation dimensions: display name -> what the score measures.
DIMENSIONS = {
    "Craft": "command of medium and technique",
    "Composition": "structural and formal strength",
    "Originality": "does it offer something not already abundant",
    "Emotional Resonance": "does it produce a felt response",
    "Conceptual Depth": "is there something to return to",
}


def _dimension_schema(measures: str) -> dict:
    return {
        "type": "object",
        "properties": {
            "Score": {
                "type": "integer",
                "description": f"1-10 rating of {measures} (5 average, 8 rare, 10 once-in-a-career).",
            },
            "Reasoning": {
                "type": "string",
                "description": "One or two sentences justifying the score.",
            },
        },
        "required": ["Score", "Reasoning"],
    }


def review_schema() -> dict:
    """JSON Schema for the review tool — used as-is by Claude (input_schema)
    and OpenAI (function parameters), and converted for Gemini."""
    return {
        "type": "object",
        "properties": {
            "First Impression": {
                "type": "string",
                "description": "2-3 sentences of immediate, honest reaction before any analysis.",
            },
            "Interpretation": {
                "type": "string",
                "description": (
                    "What this work is doing or attempting — read its subject, formal "
                    "choices (composition, color, mark-making, material) and what they "
                    "add up to. Interpret, do not merely describe what is visible."
                ),
            },
            "Evaluation": {
                "type": "object",
                "properties": {
                    name: _dimension_schema(measures)
                    for name, measures in DIMENSIONS.items()
                },
                "required": list(DIMENSIONS),
            },
            "Verdict": {
                "type": "object",
                "properties": {
                    "Overall Score": {
                        "type": "integer",
                        "description": "0-100 holistic judgment of the work — not an average of the dimension scores.",
                    },
                    "Decision": {
                        "type": "string",
                        "enum": ["ACQUIRE", "PASS"],
                        "description": "ACQUIRE or PASS. Roughly half of competent works should still be PASS.",
                    },
                    "Rational": {
                        "type": "string",
                        "description": "2-3 sentences justifying the decision. Take a position; do not hedge.",
                    },
                },
                "required": ["Overall Score", "Decision", "Rational"],
            },
        },
        "required": ["First Impression", "Interpretation", "Evaluation", "Verdict"],
    }


def _gemini_schema(node: dict, types):
    """Convert a JSON-Schema dict (review_schema) into a google-genai
    types.Schema, recursively. Supports object/string/integer + enum."""
    t = node["type"]
    if t == "object":
        return types.Schema(
            type="OBJECT",
            properties={
                key: _gemini_schema(sub, types)
                for key, sub in node["properties"].items()
            },
            required=node.get("required", []),
        )
    if t == "integer":
        return types.Schema(type="INTEGER", description=node.get("description"))
    # string
    kwargs = {"description": node.get("description")}
    if "enum" in node:
        kwargs["enum"] = node["enum"]
    return types.Schema(type="STRING", **kwargs)


def _reorder(d: dict, keys) -> dict:
    """Return d with the given keys first (in order), then any extras."""
    if not isinstance(d, dict):
        return d
    out = {k: d[k] for k in keys if k in d}
    for k, v in d.items():
        out.setdefault(k, v)
    return out


def canonicalize_review(review: dict) -> dict:
    """Reorder a model-returned review to match json-template.json. Tool
    calls return arguments as an unordered map, so providers emit keys in
    arbitrary order — this rebuilds the object in the canonical order."""
    if not isinstance(review, dict):
        return review
    out = _reorder(review, ["First Impression", "Interpretation", "Evaluation", "Verdict"])
    ev = out.get("Evaluation")
    if isinstance(ev, dict):
        ev = _reorder(ev, list(DIMENSIONS))
        out["Evaluation"] = {
            dim: _reorder(val, ["Score", "Reasoning"])
            for dim, val in ev.items()
        }
    v = out.get("Verdict")
    if isinstance(v, dict):
        out["Verdict"] = _reorder(v, ["Overall Score", "Decision", "Rational"])
    return out


def _error_review(message: str) -> dict:
    """Wrap an error/refusal into the review shape so the UI renders it
    consistently (message in First Impression, the rest left blank)."""
    return {
        "First Impression": message,
        "Interpretation": "",
        "Evaluation": {
            name: {"Score": 0, "Reasoning": ""} for name in DIMENSIONS
        },
        "Verdict": {"Overall Score": 0, "Decision": "", "Rational": ""},
    }


def build_user_prompt(description: str = "", preferences: str = "") -> str:
    """Compose the user message: the base ask plus any optional context
    (artwork description, collector preferences) provided via the web UI.
    The system prompt (INSTRUCTION) stays the shared source of truth."""
    parts = [USER_PROMPT]
    if description and description.strip():
        parts.append(
            "Artwork description (provided by the submitter):\n"
            + description.strip()
        )
    if preferences and preferences.strip():
        parts.append(
            "Collector preferences to weigh in your judgment:\n"
            + preferences.strip()
        )
    return "\n\n".join(parts)

# Models that reject temperature/top_p at the API level (Claude 4.7+ and
# Fable removed sampling params; OpenAI's gpt-5/o-series reasoning models
# only accept the default). For these, knobs are silently skipped.
NO_SAMPLING_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-fable",
    "claude-mythos",
    "gpt-5",
    "o1",
    "o3",
    "o4",
)


def env_knobs() -> dict:
    """Optional sampling knobs from env — fallback when no explicit
    knobs are passed (e.g. CLI runs)."""
    out = {}
    if temp := os.environ.get("ART_REVIEWER_TEMPERATURE"):
        out["temperature"] = float(temp)
    if top_p := os.environ.get("ART_REVIEWER_TOP_P"):
        out["top_p"] = float(top_p)
    if max_tokens := os.environ.get("ART_REVIEWER_MAX_TOKENS"):
        out["max_tokens"] = int(max_tokens)
    return out


def allows_sampling(model: str) -> bool:
    return not model.startswith(NO_SAMPLING_PREFIXES)


def review_gemini(model: str, image: bytes, mime: str, k: dict, prompt: str) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY
    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=REVIEW_TOOL_NAME,
                description=REVIEW_TOOL_DESCRIPTION,
                parameters=_gemini_schema(review_schema(), types),
            )
        ]
    )
    config = types.GenerateContentConfig(
        system_instruction=INSTRUCTION,
        temperature=k.get("temperature"),
        top_p=k.get("top_p"),
        max_output_tokens=k.get("max_tokens"),
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY", allowed_function_names=[REVIEW_TOOL_NAME]
            )
        ),
    )
    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=image, mime_type=mime), prompt],
        config=config,
    )
    calls = response.function_calls
    if not calls:
        return _error_review("[Gemini returned no structured review.]")
    return dict(calls[0].args)


def review_claude(model: str, image: bytes, mime: str, k: dict, prompt: str) -> dict:
    import anthropic

    kwargs = {}
    if allows_sampling(model):
        if "temperature" in k:
            kwargs["temperature"] = k["temperature"]
        if "top_p" in k:
            kwargs["top_p"] = k["top_p"]
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    response = client.messages.create(
        model=model,
        max_tokens=k.get("max_tokens", 16000),
        system=INSTRUCTION,
        tools=[
            {
                "name": REVIEW_TOOL_NAME,
                "description": REVIEW_TOOL_DESCRIPTION,
                "input_schema": review_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": REVIEW_TOOL_NAME},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": base64.standard_b64encode(image).decode(),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        **kwargs,
    )
    if response.stop_reason == "refusal":
        return _error_review("[Claude declined this request (stop_reason: refusal).]")
    block = next((b for b in response.content if b.type == "tool_use"), None)
    if block is None:
        return _error_review("[Claude returned no structured review.]")
    return dict(block.input)


def review_openai(model: str, image: bytes, mime: str, k: dict, prompt: str) -> dict:
    from openai import OpenAI

    kwargs = {}
    if allows_sampling(model):
        if "temperature" in k:
            kwargs["temperature"] = k["temperature"]
        if "top_p" in k:
            kwargs["top_p"] = k["top_p"]
    if "max_tokens" in k:
        kwargs["max_completion_tokens"] = k["max_tokens"]
    data_url = f"data:{mime};base64,{base64.standard_b64encode(image).decode()}"
    client = OpenAI()  # reads OPENAI_API_KEY
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": INSTRUCTION},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": REVIEW_TOOL_NAME,
                    "description": REVIEW_TOOL_DESCRIPTION,
                    "parameters": review_schema(),
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": REVIEW_TOOL_NAME}},
        **kwargs,
    )
    calls = response.choices[0].message.tool_calls
    if not calls:
        return _error_review("[OpenAI returned no structured review.]")
    return json.loads(calls[0].function.arguments)


def review_image(
    model: str,
    image: bytes,
    mime: str,
    knobs: dict | None = None,
    description: str = "",
    preferences: str = "",
) -> dict:
    """Core dispatch — used by both the CLI below and the web UI server.

    Returns the structured review object (one string per section, keys per
    json-template.json), produced via provider tool calling.

    knobs: optional {temperature, top_p, max_tokens}; falls back to the
    ART_REVIEWER_* env vars when not given.
    description / preferences: optional free-text context appended to the
    user message (the system prompt stays fixed).
    """
    k = knobs if knobs is not None else env_knobs()
    prompt = build_user_prompt(description, preferences)
    # Tolerate LiteLLM-style "provider/model" IDs from the ADK build.
    model = model.split("/", 1)[-1]
    if model.startswith("gemini"):
        result = review_gemini(model, image, mime, k, prompt)
    elif model.startswith("claude"):
        result = review_claude(model, image, mime, k, prompt)
    else:
        result = review_openai(model, image, mime, k, prompt)
    return canonicalize_review(result)


def review(model: str, image_path: Path) -> dict:
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    return review_image(model, image_path.read_bytes(), mime)


def main() -> None:
    parser = argparse.ArgumentParser(description="Review an artwork image.")
    parser.add_argument("image", type=Path, help="path to the artwork image")
    parser.add_argument(
        "--model",
        default=os.environ.get("ART_REVIEWER_MODEL", DEFAULT_MODEL),
        help="model ID (default: $ART_REVIEWER_MODEL or %(default)s)",
    )
    args = parser.parse_args()

    if not args.image.is_file():
        sys.exit(f"error: no such image: {args.image}")

    print(f"--- model: {args.model} ---\n", file=sys.stderr)
    print(json.dumps(review(args.model, args.image), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
