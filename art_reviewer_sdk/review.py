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


def review_gemini(model: str, image: bytes, mime: str, k: dict) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY
    config = types.GenerateContentConfig(
        system_instruction=INSTRUCTION,
        temperature=k.get("temperature"),
        top_p=k.get("top_p"),
        max_output_tokens=k.get("max_tokens"),
    )
    response = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=image, mime_type=mime), USER_PROMPT],
        config=config,
    )
    return response.text


def review_claude(model: str, image: bytes, mime: str, k: dict) -> str:
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
                    {"type": "text", "text": USER_PROMPT},
                ],
            }
        ],
        **kwargs,
    )
    if response.stop_reason == "refusal":
        return "[Claude declined this request (stop_reason: refusal).]"
    return "".join(b.text for b in response.content if b.type == "text")


def review_openai(model: str, image: bytes, mime: str, k: dict) -> str:
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
                    {"type": "text", "text": USER_PROMPT},
                ],
            },
        ],
        **kwargs,
    )
    return response.choices[0].message.content


def review_image(model: str, image: bytes, mime: str, knobs: dict | None = None) -> str:
    """Core dispatch — used by both the CLI below and the web UI server.

    knobs: optional {temperature, top_p, max_tokens}; falls back to the
    ART_REVIEWER_* env vars when not given.
    """
    k = knobs if knobs is not None else env_knobs()
    # Tolerate LiteLLM-style "provider/model" IDs from the ADK build.
    model = model.split("/", 1)[-1]
    if model.startswith("gemini"):
        return review_gemini(model, image, mime, k)
    if model.startswith("claude"):
        return review_claude(model, image, mime, k)
    return review_openai(model, image, mime, k)


def review(model: str, image_path: Path) -> str:
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
    print(review(args.model, args.image))


if __name__ == "__main__":
    main()
