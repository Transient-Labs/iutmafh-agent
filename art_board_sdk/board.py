#!/usr/bin/env python3
"""Board of art reviewers.

A panel of reviewer agents each review an artwork independently, then a judge
agent sees the artwork plus all of their reviews and issues the final verdict.

This reuses the review engine in ../art_reviewer_sdk/review.py without modifying
it: each reviewer is one review_image() call with its own system prompt, and the
judge dispatches through the same provider functions with a prompt that embeds
the reviews.

System prompts live in board_prompts/ as Python modules, each defining an
INSTRUCTION string (same convention as review_prompts/review_prompt_<N>.py).
Every *.py is a reviewer on the panel EXCEPT the judge, which is the file named
by JUDGE_STEM below (currently adjudicator.py). Rename freely; to change which
file is the judge, change JUDGE_STEM.
"""

import importlib.util
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = HERE.parent / "art_reviewer_sdk"
sys.path.insert(0, str(SDK))

import review  # noqa: E402  reuses art_reviewer_sdk/review.py (loads .env + review_prompts on import)

PROMPTS_DIR = HERE / "board_prompts"

# The judge is board_prompts/<JUDGE_STEM>.py; every other *.py is a reviewer.
JUDGE_STEM = "adjudicator"

# Transient provider failures (rate limits, capacity, timeouts) are retried a few
# times before a reviewer/judge is reported as failed.
_TRANSIENT_TOKENS = (
    "rate limit", "ratelimit", "429", "resource exhausted", "quota",
    "overloaded", "unavailable", "503", "502", "500", "timeout", "timed out",
    "high demand", "try again", "temporarily", "deadline",
)
_RETRY_WAITS = (3, 8)  # seconds before the 2nd and 3rd attempts


def _err_msg(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _is_transient(exc: Exception) -> bool:
    text = _err_msg(exc).lower()
    return any(t in text for t in _TRANSIENT_TOKENS)


def _with_retry(fn, *args, **kwargs):
    """Call fn, retrying transient errors with backoff. Re-raises the last error
    if it is non-transient or the attempts are exhausted."""
    for attempt in range(len(_RETRY_WAITS) + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if attempt < len(_RETRY_WAITS) and _is_transient(exc):
                time.sleep(_RETRY_WAITS[attempt])
                continue
            raise


def load_prompt(name: str) -> str:
    """Load board_prompts/<name>.py and return its INSTRUCTION string.

    Same convention as art_reviewer_sdk/review_prompts/review_prompt_<N>.py. The
    module is executed fresh on every call (not cached in sys.modules), so editing
    a prompt is picked up on the next request without restarting the server."""
    p = PROMPTS_DIR / f"{name}.py"
    if not p.is_file():
        raise FileNotFoundError(f"board prompt not found: {p}")
    spec = importlib.util.spec_from_file_location(f"board_prompt_{name}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = getattr(mod, "INSTRUCTION", "")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{p} must define a non-empty INSTRUCTION string")
    return text


def reviewer_prompt_files() -> list[Path]:
    """The panel: every board_prompts/*.py except the judge, sorted by name."""
    return sorted(p for p in PROMPTS_DIR.glob("*.py") if p.stem != JUDGE_STEM)


# The judge (adjudicator) has its own tool/schema, distinct from the reviewers'
# submit_review. It is deliberately FLAT (no nested objects), so every provider
# — including Claude — serializes it reliably with no reassembly needed.
JUDGE_TOOL_NAME = "submit_panel_review"
JUDGE_TOOL_DESCRIPTION = (
    "Submit the panel adjudication and the board's final verdict. Score/Confidence "
    "fields are integers; the prose fields are plain sentences."
)


def panel_schema() -> dict:
    """Flat JSON Schema for the adjudicator's submit_panel_review tool."""
    return {
        "type": "object",
        "properties": {
            "Panel_Summary": {"type": "string",
                "description": "Overall strengths and weaknesses identified across the panel."},
            "Consensus": {"type": "array", "items": {"type": "string"},
                "description": "Each distinct point of substantial agreement across the reviewers, as its own list item."},
            "Key_Disagreements": {"type": "array", "items": {"type": "string"},
                "description": "Each distinct disagreement between reviewers, and why it matters, as its own list item."},
            "Decision_Analysis": {"type": "string",
                "description": "How you weighed the competing arguments to reach the verdict."},
            "Overall_Score": {"type": "integer",
                "description": "0-100 holistic score for the board's verdict on the artwork."},
            "Decision": {"type": "string", "enum": ["ACQUIRE", "PASS"],
                "description": "The board's final decision."},
            "Confidence": {"type": "integer",
                "description": "0-100 confidence in the final decision."},
            "Rationale": {"type": "string",
                "description": "Concise justification for the board's final verdict."},
        },
        "required": ["Panel_Summary", "Consensus", "Key_Disagreements",
                     "Decision_Analysis", "Overall_Score", "Decision",
                     "Confidence", "Rationale"],
    }


def _judge_openai(model, image, mime, k, prompt, instruction) -> dict:
    from openai import OpenAI
    import base64
    import json
    kwargs = {}
    if review.allows_sampling(model):
        if "temperature" in k:
            kwargs["temperature"] = k["temperature"]
        if "top_p" in k:
            kwargs["top_p"] = k["top_p"]
    if "max_tokens" in k:
        kwargs["max_completion_tokens"] = k["max_tokens"]
    data_url = f"data:{mime};base64,{base64.standard_b64encode(image).decode()}"
    client = OpenAI(timeout=review.REQUEST_TIMEOUT_S)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt}]},
        ],
        tools=[{"type": "function", "function": {
            "name": JUDGE_TOOL_NAME, "description": JUDGE_TOOL_DESCRIPTION,
            "parameters": panel_schema()}}],
        tool_choice={"type": "function", "function": {"name": JUDGE_TOOL_NAME}},
        **kwargs,
    )
    calls = resp.choices[0].message.tool_calls
    return json.loads(calls[0].function.arguments) if calls else {}


def _to_gemini_schema(node, types):
    """JSON Schema -> google-genai types.Schema, with array support (review.py's
    converter only handles object/string/integer, and the panel schema has arrays)."""
    t = node["type"]
    if t == "object":
        return types.Schema(type="OBJECT",
            properties={k: _to_gemini_schema(v, types) for k, v in node["properties"].items()},
            required=node.get("required", []))
    if t == "array":
        return types.Schema(type="ARRAY", items=_to_gemini_schema(node["items"], types),
            description=node.get("description"))
    if t == "integer":
        return types.Schema(type="INTEGER", description=node.get("description"))
    kwargs = {"description": node.get("description")}
    if "enum" in node:
        kwargs["enum"] = node["enum"]
    return types.Schema(type="STRING", **kwargs)


def _judge_gemini(model, image, mime, k, prompt, instruction) -> dict:
    from google import genai
    from google.genai import types
    client = genai.Client(http_options=types.HttpOptions(timeout=review.REQUEST_TIMEOUT_S * 1000))
    tool = types.Tool(function_declarations=[types.FunctionDeclaration(
        name=JUDGE_TOOL_NAME, description=JUDGE_TOOL_DESCRIPTION,
        parameters=_to_gemini_schema(panel_schema(), types))])
    config = types.GenerateContentConfig(
        system_instruction=instruction,
        temperature=k.get("temperature"), top_p=k.get("top_p"),
        max_output_tokens=k.get("max_tokens"), tools=[tool],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
            mode="ANY", allowed_function_names=[JUDGE_TOOL_NAME])))
    resp = client.models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=image, mime_type=mime), prompt],
        config=config)
    calls = resp.function_calls
    return dict(calls[0].args) if calls else {}


def _judge_claude(model, image, mime, k, prompt, instruction) -> dict:
    import anthropic
    import base64
    client = anthropic.Anthropic(timeout=review.REQUEST_TIMEOUT_S)
    tool = {"name": JUDGE_TOOL_NAME, "description": JUDGE_TOOL_DESCRIPTION,
            "input_schema": panel_schema()}  # flat + underscore keys: Claude-safe as-is
    user_content = [
        {"type": "image", "source": {"type": "base64", "media_type": mime,
                                     "data": base64.standard_b64encode(image).decode()}},
        {"type": "text", "text": prompt}]
    max_tokens = k.get("max_tokens", 16000)

    kwargs = {}
    thinking = review.claude_thinking_kwargs(model)
    if thinking:  # extended thinking forbids forced tool_choice + sampling
        kwargs.update(thinking)
        tool_choice = {"type": "auto"}
    else:
        tool_choice = {"type": "tool", "name": JUDGE_TOOL_NAME}
        if review.allows_sampling(model):
            if "temperature" in k:
                kwargs["temperature"] = k["temperature"]
            if "top_p" in k:
                kwargs["top_p"] = k["top_p"]

    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=instruction, tools=[tool],
        tool_choice=tool_choice,
        messages=[{"role": "user", "content": user_content}], **kwargs)
    if resp.stop_reason == "refusal":
        return {}
    block = next((b for b in resp.content if b.type == "tool_use"), None)
    data = dict(block.input) if block is not None else {}
    if data.get("Decision"):
        return data

    # With thinking on we must use tool_choice=auto, and Sonnet 5 sometimes answers
    # in prose, or calls the tool without filling the verdict. Force a non-thinking
    # follow-up (forcing a tool is only allowed with thinking off) so it must submit
    # a complete verdict, handing it its own analysis to convert. Retry a couple of
    # times since forced tool use still does not guarantee every required field.
    analysis = "".join(getattr(b, "text", "") for b in resp.content
                       if getattr(b, "type", None) == "text") or "(see analysis above)"
    submit_msg = ("Now submit your adjudication and the board's final verdict by calling "
                  "the submit_panel_review tool. Fill every field, including Overall_Score, "
                  "Decision (ACQUIRE or PASS), Confidence, and Rationale.")
    for _ in range(2):
        follow = client.messages.create(
            model=model, max_tokens=max_tokens, system=instruction, tools=[tool],
            tool_choice={"type": "tool", "name": JUDGE_TOOL_NAME},
            messages=[
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": analysis},
                {"role": "user", "content": submit_msg},
            ])
        fblock = next((b for b in follow.content if b.type == "tool_use"), None)
        fdata = dict(fblock.input) if fblock is not None else {}
        if fdata.get("Decision"):
            return fdata
        data = fdata or data
    return data


def _as_points(v):
    """Consensus / Key_Disagreements are arrays, but Claude occasionally returns a
    JSON-array *string* instead of a real array — parse that back to a list. Plain
    strings are left as-is (the UI renders / splits numbered points)."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                import json
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            except ValueError:
                pass
    return v


def _reassemble_panel(flat: dict) -> dict:
    """Shape the flat panel tool output into the nested form the UI renders."""
    if not isinstance(flat, dict):
        return {}
    flat = {k: review._unwrap_text(v) for k, v in flat.items()}  # unwrap Claude {"text": ...}
    return {
        "Panel Summary": flat.get("Panel_Summary"),
        "Consensus": _as_points(flat.get("Consensus")),
        "Key Disagreements": _as_points(flat.get("Key_Disagreements")),
        "Decision Analysis": flat.get("Decision_Analysis"),
        "Final Verdict": {
            "Overall Score": review._as_int(flat.get("Overall_Score")),
            "Decision": flat.get("Decision"),
            "Confidence": review._as_int(flat.get("Confidence")),
            "Rationale": flat.get("Rationale"),
        },
    }


def _judge_dispatch(model: str, image: bytes, mime: str, prompt: str,
                    instruction: str, knobs: dict | None = None) -> dict:
    """Run the adjudicator: same provider machinery as the reviewers, but with the
    submit_panel_review tool/schema and our composed prompt (embedding the reviews)."""
    k = knobs if knobs is not None else review.env_knobs()
    image, mime = review.resize_image(image, mime)
    m = model.split("/", 1)[-1]  # tolerate LiteLLM-style provider/model ids
    if m.startswith("gemini"):
        raw = _judge_gemini(m, image, mime, k, prompt, instruction)
    elif m.startswith("claude"):
        raw = _judge_claude(m, image, mime, k, prompt, instruction)
    else:
        raw = _judge_openai(m, image, mime, k, prompt, instruction)
    result = _reassemble_panel(raw)
    if not (result.get("Final Verdict") or {}).get("Decision"):
        # No verdict came back — surface it as an error rather than a blank card.
        raise RuntimeError("the adjudicator did not return a final verdict")
    return result


def _format_review(name: str, rev: dict) -> str:
    """Render one reviewer's structured review to text for the judge's prompt."""
    if not isinstance(rev, dict):
        return f"### {name}\n(no structured review returned)\n"
    ev = rev.get("Evaluation", {}) or {}
    dims = "\n".join(
        f"  - {dim}: {(ev[dim] or {}).get('Score')}/10 — {(ev[dim] or {}).get('Reasoning', '')}"
        for dim in ev if isinstance(ev.get(dim), dict)
    )
    v = rev.get("Verdict", {}) or {}
    return (
        f"### {name}\n"
        f"First impression: {rev.get('First Impression', '')}\n"
        f"Interpretation: {rev.get('Interpretation', '')}\n"
        f"Dimension scores:\n{dims}\n"
        f"Verdict: {v.get('Decision', '')} — overall {v.get('Overall Score', '')}/100\n"
        f"Rationale: {v.get('Rational', '')}\n"
    )


def _reviewer_name(path: Path) -> str:
    return path.stem.replace("_", " ").title()


def _run_reviewer(model, image_bytes, mime, path: Path, ctx: dict) -> dict:
    """One reviewer: review_image with that reviewer's system prompt. Transient
    provider errors are retried; a persistent error propagates to the caller."""
    rev = _with_retry(review.review_image, model, image_bytes, mime,
                      instruction=load_prompt(path.stem), **ctx)
    return {"name": _reviewer_name(path), "prompt": path.stem, "review": rev}


def _split_reviewers(reviewers: list) -> tuple[list, list]:
    """Partition reviewer results into (completed, failed). A failed entry has an
    'error' key and no usable 'review'."""
    ok = [r for r in reviewers if r and r.get("review") is not None]
    failed = [r for r in reviewers if not (r and r.get("review") is not None)]
    return ok, failed


def _build_judge_prompt(ctx: dict, reviewers: list[dict], failed: list[dict] | None = None) -> str:
    """The adjudicator's user message: the context plus the completed reviews. If
    any reviewers failed, the judge is told, so it adjudicates on an incomplete
    panel honestly instead of assuming all four weighed in."""
    panel = "\n\n".join(_format_review(r["name"], r["review"]) for r in reviewers)
    note = ""
    if failed:
        who = ", ".join(r["name"] for r in failed)
        note = (f"\n\nNOTE: {len(failed)} of the board's reviewers could not complete a "
                f"review ({who}) because of a provider error, so their assessment is "
                f"unavailable. Adjudicate only on the reviews that are present, and account "
                f"for the incomplete panel rather than assuming full agreement.")
    return (
        review.build_user_prompt(**ctx)
        + "\n\nA panel of independent reviewers on your board has already reviewed "
          "this artwork. Their reviews follow.\n\n" + panel + note
        + "\n\nWeigh these reviews together with the artwork itself, then submit your "
          "own review and the board's ultimate verdict."
    )


def _run_reviewer_safe(model, image_bytes, mime, path: Path, ctx: dict) -> dict:
    """_run_reviewer, but a persistent failure returns an {'error': ...} entry
    instead of raising, so one reviewer's failure does not abort the board."""
    try:
        return _run_reviewer(model, image_bytes, mime, path, ctx)
    except Exception as exc:
        return {"name": _reviewer_name(path), "prompt": path.stem, "error": _err_msg(exc)}


def run_board(model: str, image_bytes: bytes, mime: str, *,
              description: str = "", preferences: str = "",
              artwork_name: str = "", artist: str = "", work_type: str = "",
              media_note: str = "") -> dict:
    """Run the full board on one artwork and return the panel plus the judge's
    final verdict. A reviewer that persistently fails appears as an {'error': ...}
    entry; if every reviewer fails, this raises."""
    ctx = dict(description=description, preferences=preferences,
               artwork_name=artwork_name, artist=artist, work_type=work_type,
               media_note=media_note)
    files = reviewer_prompt_files()
    if not files:
        raise FileNotFoundError(f"no reviewer prompts found in {PROMPTS_DIR}")
    # Reviewers are independent, so run them concurrently (each is a blocking
    # provider call; the GIL is released during the network wait).
    with ThreadPoolExecutor(max_workers=len(files)) as pool:
        reviewers = list(pool.map(lambda f: _run_reviewer_safe(model, image_bytes, mime, f, ctx), files))
    ok, failed = _split_reviewers(reviewers)
    if not ok:
        raise RuntimeError("every reviewer failed: "
                           + " | ".join(r.get("error", "") for r in failed))
    judge = _with_retry(_judge_dispatch, model, image_bytes, mime,
                        _build_judge_prompt(ctx, ok, failed), load_prompt(JUDGE_STEM))
    return {"model": model, "reviewers": reviewers, "judge": judge}


def run_board_stream(model: str, image_bytes: bytes, mime: str, *,
                     description: str = "", preferences: str = "",
                     artwork_name: str = "", artist: str = "", work_type: str = "",
                     media_note: str = ""):
    """Generator form of run_board, yielding progress events as dicts so the UI
    can animate: 'start' (panel names), a 'reviewer_done' as EACH reviewer finishes
    (carrying either 'review' or 'error'), 'adjudicator_start' once the panel is in,
    then a final 'done' — or an 'error' event if every reviewer or the judge fails."""
    ctx = dict(description=description, preferences=preferences,
               artwork_name=artwork_name, artist=artist, work_type=work_type,
               media_note=media_note)
    files = reviewer_prompt_files()
    if not files:
        yield {"type": "error", "message": f"no reviewer prompts found in {PROMPTS_DIR}"}
        return
    names = [_reviewer_name(f) for f in files]
    yield {"type": "start", "model": model, "reviewers": names}

    reviewers: list = [None] * len(files)
    with ThreadPoolExecutor(max_workers=len(files)) as pool:
        futs = {pool.submit(_run_reviewer_safe, model, image_bytes, mime, files[i], ctx): i
                for i in range(len(files))}
        for fut in as_completed(futs):
            i = futs[fut]
            reviewers[i] = fut.result()  # _run_reviewer_safe never raises
            if reviewers[i].get("error"):
                yield {"type": "reviewer_done", "index": i, "name": names[i],
                       "error": reviewers[i]["error"]}
            else:
                yield {"type": "reviewer_done", "index": i, "name": names[i],
                       "review": reviewers[i]["review"]}

    ok, failed = _split_reviewers(reviewers)
    if not ok:
        yield {"type": "error",
               "message": "Every reviewer failed to return a review. "
                          + (failed[0].get("error", "") if failed else "")}
        return

    yield {"type": "adjudicator_start"}
    try:
        judge = _with_retry(_judge_dispatch, model, image_bytes, mime,
                            _build_judge_prompt(ctx, ok, failed), load_prompt(JUDGE_STEM))
    except Exception as exc:
        yield {"type": "error", "message": _err_msg(exc)}
        return
    yield {"type": "done", "model": model, "reviewers": reviewers, "judge": judge}
