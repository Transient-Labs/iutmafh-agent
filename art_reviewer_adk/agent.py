"""Art review agent — Chapter 1 of "I Used To Make Art For Humans".

A single reviewer agent whose underlying model is swappable across
Gemini, Claude, and OpenAI via the ART_REVIEWER_MODEL env var, so the
same critic persona can be benchmarked across providers.

Examples:
    ART_REVIEWER_MODEL=gemini-2.5-flash            (native ADK)
    ART_REVIEWER_MODEL=anthropic/claude-opus-4-8   (via LiteLLM)
    ART_REVIEWER_MODEL=openai/gpt-5.1              (via LiteLLM)
"""

import os

from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

DEFAULT_MODEL = "gemini-2.5-flash"


def resolve_model(model_id: str):
    """Gemini IDs are passed straight to ADK; everything else routes
    through LiteLLM (expects a provider prefix, e.g. "anthropic/...")."""
    if model_id.startswith("gemini"):
        return model_id
    return LiteLlm(model=model_id)


# Shared with art_reviewer_sdk — single source of truth for the persona.
from review_prompt import INSTRUCTION

def generation_config() -> types.GenerateContentConfig | None:
    """Sampling knobs, all optional, all driven by env vars so a test
    harness can sweep them without code changes:

        ART_REVIEWER_TEMPERATURE   e.g. 0.2 (deterministic) .. 1.0+ (varied)
        ART_REVIEWER_TOP_P         nucleus sampling, e.g. 0.95
        ART_REVIEWER_MAX_TOKENS    cap on review length

    Unset knobs fall back to the provider's defaults.
    """
    cfg = {}
    if temp := os.environ.get("ART_REVIEWER_TEMPERATURE"):
        cfg["temperature"] = float(temp)
    if top_p := os.environ.get("ART_REVIEWER_TOP_P"):
        cfg["top_p"] = float(top_p)
    if max_tokens := os.environ.get("ART_REVIEWER_MAX_TOKENS"):
        cfg["max_output_tokens"] = int(max_tokens)
    return types.GenerateContentConfig(**cfg) if cfg else None


root_agent = Agent(
    model=resolve_model(os.environ.get("ART_REVIEWER_MODEL", DEFAULT_MODEL)),
    name="art_reviewer",
    description="Reviews artworks from images, producing a structured critique with scores and an acquire/pass verdict.",
    instruction=INSTRUCTION,
    generate_content_config=generation_config(),
)
