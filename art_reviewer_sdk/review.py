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
import io
import json
import mimetypes
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# Versioned system prompts live in review_prompts/ next to this file; putting
# the directory on sys.path keeps `review_prompt_<N>` importable as a module
# (see load_instruction).
PROMPTS_DIR = Path(__file__).resolve().parent / "review_prompts"
sys.path.insert(0, str(PROMPTS_DIR))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / ".env")

from review_prompt_1 import INSTRUCTION

DEFAULT_MODEL = "gemini-2.5-flash"
USER_PROMPT = "Review this artwork."

# Hard per-request timeout for every provider. Without one, a provider under
# load can hold the connection open indefinitely and hang the whole workbook
# run (observed with Gemini previews during "high demand" spikes).
REQUEST_TIMEOUT_S = 180


# The review is returned as structured tool input following this schema —
# keys and nesting match json-template.json exactly so the web UI can render
# and store them directly. Descriptions are deliberately neutral (structure
# only, no calibration or rubric language): the selected review_prompt_<N>
# system prompt must be the ONLY instruction source, or prompt-version
# comparisons in the workbook are confounded.
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
                "description": f"1-10 rating of {measures}.",
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
                        "description": "ACQUIRE or PASS.",
                    },
                    "Rational": {
                        "type": "string",
                        "description": "2-3 sentences justifying the decision.",
                    },
                },
                "required": ["Overall Score", "Decision", "Rational"],
            },
        },
        "required": ["First Impression", "Interpretation", "Evaluation", "Verdict"],
    }


def claude_flat_schema() -> dict:
    """A flattened, single-level tool schema for Claude. Claude models under
    forced tool use unreliably serialize the nested review_schema — they
    stringify sub-objects or mis-nest Verdict inside Evaluation — because the
    nesting is what they trip on. A schema of only scalar fields removes that
    failure mode entirely. The flat response is rebuilt into the canonical
    nested review by reassemble_flat_review(). OpenAI and Gemini keep the nested
    review_schema, which they serialize reliably."""
    props = {
        "First_Impression": {
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
    }
    for name, measures in DIMENSIONS.items():
        san = name.replace(" ", "_")
        props[f"{san}_Score"] = {
            "type": "integer",
            "description": f"1-10 rating of {measures} ({name}).",
        }
        props[f"{san}_Reasoning"] = {
            "type": "string",
            "description": f"One or two sentences justifying the {name} score.",
        }
    props["Overall_Score"] = {
        "type": "integer",
        "description": "0-100 holistic judgment of the work — not an average of the dimension scores.",
    }
    props["Decision"] = {
        "type": "string",
        "enum": ["ACQUIRE", "PASS"],
        "description": "ACQUIRE or PASS.",
    }
    props["Rational"] = {
        "type": "string",
        "description": "2-3 sentences justifying the decision.",
    }
    return {"type": "object", "properties": props, "required": list(props)}


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


# Claude requires tool input_schema property keys to match
# ^[a-zA-Z0-9_.-]{1,64}$ — no spaces. Our display keys (e.g. "First Impression",
# "Overall Score") contain spaces, so for Claude we send a space->underscore
# sanitized schema and restore the display keys on the way back. Gemini and
# OpenAI accept the spaced keys directly.
_DISPLAY_KEYS = [
    "First Impression", "Interpretation", "Evaluation", "Verdict",
    *DIMENSIONS, "Score", "Reasoning", "Overall Score", "Decision", "Rational",
]
_DISPLAY_FROM_SANITIZED = {k.replace(" ", "_"): k for k in _DISPLAY_KEYS}


def _sanitize_schema_keys(node: dict) -> dict:
    """Recursively replace spaces in object property keys with underscores,
    returning a copy (the original review_schema is left untouched)."""
    if not isinstance(node, dict):
        return node
    if node.get("type") == "object" and "properties" in node:
        node = dict(node)
        node["properties"] = {
            key.replace(" ", "_"): _sanitize_schema_keys(sub)
            for key, sub in node["properties"].items()
        }
        if "required" in node:
            node["required"] = [r.replace(" ", "_") for r in node["required"]]
    return node


def _restore_keys(obj):
    """Recursively map sanitized underscore keys back to their display form."""
    if isinstance(obj, dict):
        return {_DISPLAY_FROM_SANITIZED.get(k, k): _restore_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_restore_keys(x) for x in obj]
    return obj


def _unwrap_text(v):
    """Claude sometimes returns a scalar field wrapped as {"text": "..."};
    unwrap it back to the bare value."""
    if isinstance(v, dict) and list(v.keys()) == ["text"] and isinstance(v["text"], (str, int, float)):
        return v["text"]
    return v


def _lenient_json_object(s):
    """Parse a JSON-object string that Claude closed prematurely and then
    appended more key/value pairs to, e.g. '{dims}, "Verdict": {...}}' — a valid
    object followed by trailing fragments that json.loads rejects as "Extra
    data". Reads the leading object, then folds each trailing ', "Key": value'
    fragment into it. Returns the merged dict, or None if nothing parses."""
    dec = json.JSONDecoder()
    s = s.strip()
    try:
        obj, end = dec.raw_decode(s)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return obj
    merged = dict(obj)
    rest = s[end:].lstrip()
    while rest.startswith(","):
        rest = rest[1:].lstrip()
        wrapped = "{" + rest
        try:
            frag, fend = dec.raw_decode(wrapped)
        except ValueError:
            break
        if isinstance(frag, dict):
            merged.update(frag)
        rest = wrapped[fend:].lstrip()
        while rest.startswith("}"):  # drop the stray closer(s) from the early close
            rest = rest[1:].lstrip()
    return merged


def _maybe_json(v):
    """Claude sometimes emits a nested object as a JSON *string* instead of a
    real object. Parse it back when it looks like JSON (tolerating a prematurely
    closed object with trailing fragments); otherwise leave it."""
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in "{[":
            try:
                return json.loads(s)
            except ValueError:
                obj = _lenient_json_object(s)
                return obj if obj is not None else v
    return v


def _as_int(v):
    """Coerce a score the model returned as a float or numeric string back to
    int; leave anything else (including None) untouched."""
    if isinstance(v, bool) or v is None or isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v.strip())
        except ValueError:
            try:
                return int(float(v.strip()))
            except ValueError:
                return v
    return v


def reassemble_flat_review(flat) -> dict:
    """Rebuild the canonical nested review (display keys) from Claude's flat
    tool response (claude_flat_schema). Missing fields stay None so an
    incomplete response still surfaces as a null rather than a crash."""
    if not isinstance(flat, dict):
        return flat
    evaluation = {}
    for name in DIMENSIONS:
        san = name.replace(" ", "_")
        evaluation[name] = {
            "Score": _as_int(flat.get(f"{san}_Score")),
            "Reasoning": flat.get(f"{san}_Reasoning"),
        }
    return {
        "First Impression": flat.get("First_Impression"),
        "Interpretation": flat.get("Interpretation"),
        "Evaluation": evaluation,
        "Verdict": {
            "Overall Score": _as_int(flat.get("Overall_Score")),
            "Decision": flat.get("Decision"),
            "Rational": flat.get("Rational"),
        },
    }


def _coerce_claude_input(raw):
    """Repair the malformed-but-recoverable tool inputs Claude models emit under
    forced tool use. Runs in sanitized (underscore) key space, before
    _restore_keys. Handles three drift modes seen from Claude (esp. Haiku and
    Sonnet 5): scalars wrapped as {"text": ...}, nested objects returned as JSON
    strings, and a Verdict nested inside Evaluation. The data is present in every
    case — this reshapes it to the schema so the review is not lost as a null."""
    if not isinstance(raw, dict):
        return raw
    out = {k: _unwrap_text(v) for k, v in raw.items()}
    # A nested object arriving as a JSON string (Evaluation or Verdict).
    for key in ("Evaluation", "Verdict"):
        if key in out:
            out[key] = _maybe_json(out[key])
    # A Verdict emitted inside Evaluation — lift it back to the top level.
    ev = out.get("Evaluation")
    if isinstance(ev, dict) and "Verdict" in ev:
        embedded = _maybe_json(ev.pop("Verdict"))
        if not isinstance(out.get("Verdict"), dict):
            out["Verdict"] = embedded
    return out


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


def build_user_prompt(
    description: str = "",
    preferences: str = "",
    artwork_name: str = "",
    artist: str = "",
    price: str = "",
    work_type: str = "",
    max_spend: str = "",
    media_note: str = "",
) -> str:
    """Compose the user message: the base ask plus any optional context
    (artwork name, artist, work type, price, maximum spend, description,
    collector preferences) provided via the web UI. The system prompt
    (INSTRUCTION) stays the shared source of truth — blank fields are omitted."""
    parts = [USER_PROMPT]
    if artwork_name and artwork_name.strip():
        parts.append("Artwork title: " + artwork_name.strip())
    if artist and artist.strip():
        parts.append("Artist: " + artist.strip())
    if work_type and work_type.strip():
        parts.append("Work type: " + work_type.strip())
    if media_note and media_note.strip():
        parts.append("Media note: " + media_note.strip())
    if price and price.strip():
        parts.append("Listed price (USD): " + price.strip())
    if max_spend and max_spend.strip():
        parts.append("Maximum spend on this work (USD): " + max_spend.strip())
    if description and description.strip():
        parts.append(
            "Artwork description (provided by the submitter):\n"
            + description.strip()
        )
    if preferences and preferences.strip():
        parts.append(
            "The collector's stated preferences (tendencies, not rules — "
            "exceptional work outside them can still merit acquisition):\n"
            + preferences.strip()
        )
    return "\n\n".join(parts)


def load_instruction(version) -> str:
    """Import review_prompts/review_prompt_<version>.py and return its
    INSTRUCTION text. `version` may be a bare number (1 -> review_prompt_1)
    or a full module name. Raises ValueError if the module or its
    INSTRUCTION is missing."""
    import importlib

    name = f"review_prompt_{version}" if str(version).strip().isdigit() else str(version).strip()
    try:
        mod = importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise ValueError(f"review-prompt module '{name}' not found") from exc
    instruction = getattr(mod, "INSTRUCTION", "")
    if not instruction:
        raise ValueError(f"{name} defines no INSTRUCTION")
    return instruction

# Models that reject temperature/top_p at the API level (Claude 4.7+, the
# Claude 5 family, and Fable removed sampling params; OpenAI's gpt-5/o-series
# reasoning models only accept the default). For these, knobs are silently
# skipped.
NO_SAMPLING_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-5",
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


# Reasoning parity: GPT and Gemini reason by default, but Claude's extended
# thinking is off unless requested. We enable it so all three families reason,
# using each Claude generation's own API: Claude 5+ uses adaptive thinking (the
# model decides effort, like Gemini's dynamic default), Claude 4.x takes an
# explicit token budget. Thinking also forbids forced tool_choice and sampling
# params, so the Claude path below switches to tool_choice=auto and drops
# temperature/top_p whenever thinking is on (see review_claude).
CLAUDE_4X_THINKING_BUDGET = 4096


def _claude_major_version(model: str) -> int:
    """Major version from a Claude model id: claude-sonnet-5 -> 5,
    claude-sonnet-4-6 -> 4, claude-haiku-4-5 -> 4. 0 if not determinable."""
    for part in model.split("-")[2:]:
        if part.isdigit():
            return int(part)
    return 0


def claude_thinking_kwargs(model: str) -> dict:
    """Extra messages.create kwargs enabling each Claude generation's default
    reasoning. Empty for anything not recognized as a thinking-capable model."""
    major = _claude_major_version(model)
    if major >= 5:
        return {"thinking": {"type": "adaptive"}}
    if major == 4:
        return {"thinking": {"type": "enabled", "budget_tokens": CLAUDE_4X_THINKING_BUDGET}}
    return {}


def review_gemini(model: str, image: bytes, mime: str, k: dict, prompt: str,
                  instruction: str = INSTRUCTION) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(  # reads GEMINI_API_KEY
        http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_S * 1000))
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
        system_instruction=instruction,
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


def review_claude(model: str, image: bytes, mime: str, k: dict, prompt: str,
                  instruction: str = INSTRUCTION) -> dict:
    import anthropic

    kwargs = {}
    thinking = claude_thinking_kwargs(model)
    if thinking:
        # Extended thinking forbids forced tool use and sampling params: let the
        # model choose the tool (it reliably does with this system prompt) and
        # leave temperature/top_p at their defaults.
        kwargs.update(thinking)
        tool_choice = {"type": "auto"}
    else:
        tool_choice = {"type": "tool", "name": REVIEW_TOOL_NAME}
        if allows_sampling(model):
            if "temperature" in k:
                kwargs["temperature"] = k["temperature"]
            if "top_p" in k:
                kwargs["top_p"] = k["top_p"]
    client = anthropic.Anthropic(timeout=REQUEST_TIMEOUT_S)  # reads ANTHROPIC_API_KEY
    response = client.messages.create(
        model=model,
        max_tokens=k.get("max_tokens", 16000),
        system=instruction,
        tools=[
            {
                "name": REVIEW_TOOL_NAME,
                "description": REVIEW_TOOL_DESCRIPTION,
                "input_schema": claude_flat_schema(),
            }
        ],
        tool_choice=tool_choice,
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
    # Claude uses the flat schema; unwrap any {"text": ...}-wrapped scalars, then
    # rebuild the canonical nested review. _coerce_claude_input stays as a net.
    return reassemble_flat_review(_coerce_claude_input(dict(block.input)))


def review_openai(model: str, image: bytes, mime: str, k: dict, prompt: str,
                  instruction: str = INSTRUCTION) -> dict:
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
    client = OpenAI(timeout=REQUEST_TIMEOUT_S)  # reads OPENAI_API_KEY
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
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


MAX_IMAGE_EDGE = 1024  # downscale uploads so the long edge is at most this many pixels


def resize_image(data: bytes, mime: str, max_edge: int = MAX_IMAGE_EDGE) -> tuple[bytes, str]:
    """Downscale an image so its long edge is at most max_edge pixels, re-encoding
    in its original format. Returns (data, mime) unchanged if the image already
    fits, isn't a decodable raster image, or can't be re-encoded — so it always
    degrades gracefully to sending the original bytes."""
    try:
        from PIL import Image
    except ImportError:
        return data, mime
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return data, mime

    if max(img.size) <= max_edge:
        return data, mime

    fmt = img.format  # "JPEG", "PNG", "WEBP", "GIF", ...
    if fmt == "MPO":
        # Multi-Picture Object: a multi-frame JPEG container some cameras
        # write with a .jpg extension. Providers reject image/mpo — re-encode
        # the primary frame as a plain JPEG instead.
        fmt = "JPEG"
    img.thumbnail((max_edge, max_edge))  # preserves aspect ratio, never upscales

    save_kwargs = {}
    if fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = 90
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")  # JPEG/WEBP can't store alpha or palette modes
    out = io.BytesIO()
    try:
        img.save(out, format=fmt or "PNG", **save_kwargs)
    except Exception:
        return data, mime

    new_mime = Image.MIME.get(fmt, mime) if fmt else mime
    return out.getvalue(), new_mime


def review_image(
    model: str,
    image: bytes,
    mime: str,
    knobs: dict | None = None,
    description: str = "",
    preferences: str = "",
    artwork_name: str = "",
    artist: str = "",
    price: str = "",
    work_type: str = "",
    max_spend: str = "",
    media_note: str = "",
    instruction: str | None = None,
) -> dict:
    """Core dispatch — used by both the CLI below and the web UI server.

    Returns the structured review object (one string per section, keys per
    json-template.json), produced via provider tool calling.

    knobs: optional {temperature, top_p, max_tokens}; falls back to the
    ART_REVIEWER_* env vars when not given.
    description / preferences / artwork_name / artist / price: optional
    free-text context appended to the user message (the system prompt stays
    fixed); blank fields are omitted.
    instruction: optional system-prompt override (e.g. the workbook harness
    selecting a review_prompt_N variant); defaults to the module INSTRUCTION.
    """
    k = knobs if knobs is not None else env_knobs()
    system = instruction if instruction is not None else INSTRUCTION
    prompt = build_user_prompt(description, preferences, artwork_name, artist, price,
                               work_type, max_spend, media_note)
    # Shrink large uploads to a 1024px long edge before sending to any provider.
    image, mime = resize_image(image, mime)
    # Tolerate LiteLLM-style "provider/model" IDs from the ADK build.
    model = model.split("/", 1)[-1]
    if model.startswith("gemini"):
        result = review_gemini(model, image, mime, k, prompt, system)
    elif model.startswith("claude"):
        result = review_claude(model, image, mime, k, prompt, system)
    else:
        result = review_openai(model, image, mime, k, prompt, system)
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
