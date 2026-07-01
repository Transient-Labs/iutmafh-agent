#!/usr/bin/env python3
"""Automated workbook test harness for the art reviewer SDK.

Runs one full "workbook" for a single artwork: every experimental condition
(A–D) against each model, N runs each, and writes every review to a single
JSON file grouped by condition. Results are saved incrementally (after each
review), so a mid-run failure loses nothing and re-running resumes the
missing slots.

Conditions (what varies — see WORKBOOK.md):
    A  Image Only
    B  Image + Artwork Description
    C  Image + Collector Preference
    D  Image + Artwork Description + Collector Preference

The condition is decided purely by which inputs the harness sends; it is
experiment metadata and is never injected into the prompt (that would bias
the model). Each output record is tagged with its condition.

Usage:
    uv run python art_reviewer_sdk/run_workbook.py testing_assets/art-001.toml
    uv run python art_reviewer_sdk/run_workbook.py assets.toml --out results/x.json --runs 3 --delay 1

The assets TOML provides one artwork's inputs:
    artwork_path  (required, resolved relative to the TOML file)
    description   (optional)
    [preferences] (optional table of named variants, e.g. related / unrelated;
                   Condition E is run once per variant)
    artwork_id / artwork_title (optional, for labelling)
"""

import argparse
import json
import mimetypes
import os
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT))  # so review_prompt_<N> modules are importable

from review import review_image, load_instruction, MAX_IMAGE_EDGE  # noqa: E402  (path set above)

# Sampling knobs passed to every review. {} means provider defaults (the
# ART_REVIEWER_* env fallback is deliberately bypassed so a stray .env value
# can't silently change the experiment). Recorded in the results JSON.
KNOBS: dict = {}

# Default workbook assets file — used when no path is passed on the CLI.
DEFAULT_ASSETS = REPO_ROOT / "testing_assets" / "workbook.toml"

# Models under test — exact API IDs (matches the workbook columns).
# MODELS = ["gpt-5-mini", "gemini-2.5-flash", "claude-haiku-4-5"]
MODELS = ["gpt-5-mini", "gemini-2.5-flash"]

# (key, label, send_description, send_artist, send_preferences)
CONDITIONS = [
    ("A", "Artwork Only", False, False, False),
    ("B", "Artwork + Description", True, False, False),
    ("C", "Artwork + Artist Name", False, True, False),
    ("D", "Artwork + Description + Artist Name", True, True, False),
    ("E", "Artwork + Description + Artist Name + Collector Preference", True, True, True),
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_assets(path: Path) -> dict:
    """Parse the per-workbook TOML and resolve the artwork path."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        sys.exit(f"error: could not read assets file {path}: {exc}")

    if "artwork_path" not in data:
        sys.exit(f"error: {path} is missing required key 'artwork_path'")

    art = Path(str(data["artwork_path"]))
    if not art.is_absolute():
        art = (path.parent / art).resolve()
    if not art.is_file():
        sys.exit(f"error: artwork image not found: {art}")

    data["artwork_path"] = str(art)
    data["description"] = str(data.get("description", "")).strip()
    data["artwork_id"] = str(data.get("artwork_id", "")).strip()
    data["artwork_title"] = str(data.get("artwork_title", "")).strip()
    data["artwork_price"] = str(data.get("artwork_price", "")).strip()
    data["max_spend"] = str(data.get("max_spend", "")).strip()
    data["artist"] = str(data.get("artist", "")).strip()
    data["work_type"] = str(data.get("work_type", "")).strip()

    # System-prompt selection: review_prompt_<N>.py. Record the version and load
    # the actual INSTRUCTION text used for every review in this workbook.
    version = data.get("review_prompt", 1)
    data["review_prompt"] = version
    try:
        data["instruction"] = load_instruction(version)
    except ValueError as exc:
        sys.exit(f"error: {exc} — set 'review_prompt' in the workbook TOML to an "
                 f"existing variant (e.g. 1 or 2)")

    # Collector preferences: a [preferences] table of named variants. Whatever
    # entries you put there, Condition E is run once per entry. A bare string
    # is also accepted (treated as a single "default" variant).
    prefs = data.get("preferences", {})
    if isinstance(prefs, str):
        prefs = {"default": prefs} if prefs.strip() else {}
    elif isinstance(prefs, dict):
        prefs = {k: str(v).strip() for k, v in prefs.items() if str(v).strip()}
    else:
        prefs = {}
    data["preferences"] = prefs
    return data


def build_skeleton(assets: dict, runs: int) -> dict:
    """Fresh output structure with empty per-condition review buckets."""
    conditions = {}
    for cond, label, use_d, use_a, use_p in CONDITIONS:
        conditions[cond] = {
            "label": label,
            "description_used": assets["description"] if use_d else "",
            "artist_used": assets["artist"] if use_a else "",
            "preference_variants": dict(assets["preferences"]) if use_p else {},
            "reviews": [],
        }
    ts = now_iso()
    return {
        "workbook": {
            "artwork_id": assets["artwork_id"],
            "artwork_title": assets["artwork_title"],
            "artist": assets["artist"],
            "work_type": assets["work_type"],
            "artwork_price": assets["artwork_price"],
            "max_spend": assets["max_spend"],
            "artwork_path": assets["artwork_path"],
            "models": MODELS,
            "runs_per_condition": runs,
            "sampling_knobs": KNOBS,  # {} = provider defaults
            "max_image_edge": MAX_IMAGE_EDGE,
            "review_prompt": assets["review_prompt"],
            "system_prompt": assets["instruction"],
            "started_at": ts,
            "updated_at": ts,
        },
        "conditions": conditions,
    }


def load_or_init(out_path: Path, assets: dict, runs: int) -> dict:
    """Build a fresh structure, or carry forward an existing file for resume.

    On resume we keep the prior reviews, started_at, and the system_prompt
    snapshot that produced them (so the prompt-drift check below is honest),
    but refresh labels / used-context from the current assets + run count.
    """
    data = build_skeleton(assets, runs)
    if not out_path.exists():
        return data

    try:
        existing = json.loads(out_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"error: --out exists but is not readable JSON ({exc}). "
                 f"Move it aside or pass a fresh --out.")

    wb = existing.get("workbook", {})
    data["workbook"]["started_at"] = wb.get("started_at", data["workbook"]["started_at"])
    stored_prompt = wb.get("system_prompt", "")
    data["workbook"]["system_prompt"] = stored_prompt or assets["instruction"]
    if stored_prompt and stored_prompt != assets["instruction"]:
        print(
            "WARNING: the system prompt has changed since this results file was\n"
            "         started (different review_prompt version or edited text).\n"
            "         Resuming will mix two different experiments — use a fresh\n"
            "         --out for the new prompt.\n",
            file=sys.stderr,
        )
    valid = {}
    for cond, _l, _ud, _ua, use_p in CONDITIONS:
        valid[cond] = set(assets["preferences"].keys()) if use_p else {None}
    for cond in data["conditions"]:
        prior = existing.get("conditions", {}).get(cond, {}).get("reviews", [])
        # Drop prior reviews that don't match the current preference-variant
        # config (e.g. a results file from before variants were introduced, or
        # a renamed/removed variant) so they get re-run rather than orphaned.
        data["conditions"][cond]["reviews"] = [
            r for r in prior if r.get("preference_variant") in valid[cond]
        ]
    return data


def completed_slots(data: dict) -> set:
    """Set of (condition, preference_variant, model, run) tuples recorded."""
    done = set()
    for cond, bucket in data["conditions"].items():
        for r in bucket.get("reviews", []):
            done.add((cond, r.get("preference_variant"), r.get("model"), r.get("run")))
    return done


def total_slots(assets: dict, runs: int) -> int:
    """Planned review count: A–D = models×runs; E = variants×models×runs."""
    t = 0
    for _cond, _l, _ud, _ua, use_p in CONDITIONS:
        nvar = len(assets["preferences"]) if use_p else 1
        t += nvar * len(MODELS) * runs
    return t


def save(out_path: Path, data: dict) -> None:
    """Atomically write the whole results structure (temp file + os.replace)."""
    data["workbook"]["updated_at"] = now_iso()
    model_index = {m: i for i, m in enumerate(MODELS)}
    for bucket in data["conditions"].values():
        bucket["reviews"].sort(key=lambda r: (
            str(r.get("preference_variant") or ""),
            model_index.get(r.get("model"), 99),
            r.get("run", 0),
        ))
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, out_path)


def summary_path_for(out_path: Path) -> Path:
    """Sibling summary file: results/ART-001.json -> results/ART-001.summary.json"""
    return out_path.with_name(out_path.stem + ".summary.json")


def write_summary(out_path: Path, data: dict) -> None:
    """Write a flat, high-level summary (condition, model, run + the Verdict
    fields) derived from the full results — for quick scanning / analysis."""
    model_index = {m: i for i, m in enumerate(MODELS)}
    rows = []
    for cond, bucket in data["conditions"].items():
        for r in bucket.get("reviews", []):
            review = r.get("review") if isinstance(r.get("review"), dict) else {}
            verdict = review.get("Verdict", {}) if isinstance(review, dict) else {}
            rows.append({
                "condition": cond,
                "preference_variant": r.get("preference_variant"),
                "model": r.get("model"),
                "run": r.get("run"),
                "overall_score": verdict.get("Overall Score"),
                "decision": verdict.get("Decision"),
                "rational": verdict.get("Rational"),
            })
    rows.sort(key=lambda x: (
        x["condition"], str(x["preference_variant"] or ""),
        model_index.get(x["model"], 99), x["run"] or 0,
    ))

    wb = data.get("workbook", {})
    summary = {
        "artwork_id": wb.get("artwork_id", ""),
        "artwork_title": wb.get("artwork_title", ""),
        "generated_at": now_iso(),
        "results": rows,
    }
    sp = summary_path_for(out_path)
    tmp = sp.with_suffix(sp.suffix + ".tmp")
    tmp.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    os.replace(tmp, sp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a full art-reviewer workbook.")
    parser.add_argument("assets", nargs="?", type=Path, default=DEFAULT_ASSETS,
                        help="path to the workbook TOML assets file (default: %(default)s)")
    parser.add_argument("--out", type=Path, default=None,
                        help="results JSON path (default: results/<artwork_id-or-stem>.json)")
    parser.add_argument("--runs", type=int, default=3, help="runs per condition per model (default: 3)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds to pause between calls (default: 0)")
    args = parser.parse_args()

    assets = load_assets(args.assets)

    if args.out is not None:
        out_path = args.out
    else:
        stem = assets["artwork_id"] or args.assets.stem
        out_path = REPO_ROOT / "results" / f"{stem}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = load_or_init(out_path, assets, args.runs)
    completed = completed_slots(data)
    write_summary(out_path, data)  # keep the summary present/current even on a no-op resume

    image_bytes = Path(assets["artwork_path"]).read_bytes()
    mime = mimetypes.guess_type(assets["artwork_path"])[0] or "image/jpeg"

    n_variants = len(assets["preferences"])
    total = total_slots(assets, args.runs)
    fail_count = 0

    label = assets["artwork_id"] or assets["artwork_title"] or args.assets.stem
    print(f"Workbook: {label}  ({total} reviews — A–D ×{args.runs} runs each; "
          f"E ×{n_variants} preference{'' if n_variants == 1 else 's'} ×{args.runs} runs)")
    if not n_variants:
        print("NOTE: no [preferences] entries found — Condition E will be skipped.",
              file=sys.stderr)
    if completed:
        print(f"Resuming — {len(completed)}/{total} already complete.")
    print(f"Output: {out_path}\n")

    try:
        for cond, _lbl, use_d, use_a, use_p in CONDITIONS:
            bucket = data["conditions"][cond]
            desc = assets["description"] if use_d else ""
            artist = assets["artist"] if use_a else ""
            variants = list(assets["preferences"].items()) if use_p else [(None, "")]
            for variant, pref in variants:
                for model in MODELS:
                    for run in range(1, args.runs + 1):
                        if (cond, variant, model, run) in completed:
                            continue
                        vtag = f"/{variant}" if variant else ""
                        tag = f"[{cond}{vtag}][{model}] run {run}/{args.runs}"
                        t0 = time.time()
                        try:
                            review = review_image(
                                model, image_bytes, mime,
                                knobs=KNOBS, description=desc, preferences=pref,
                                artist=artist, price=assets["artwork_price"],
                                work_type=assets["work_type"],
                                max_spend=assets["max_spend"],
                                instruction=assets["instruction"],
                            )
                        except Exception as exc:
                            fail_count += 1
                            print(f"[FAIL] {tag} -> {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                            if args.delay:
                                time.sleep(args.delay)
                            continue

                        secs = round(time.time() - t0, 1)
                        bucket["reviews"].append({
                            "condition": cond,
                            "model": model,
                            "preference_variant": variant,
                            "run": run,
                            "timestamp": now_iso(),
                            "seconds": secs,
                            "review": review,
                        })
                        completed.add((cond, variant, model, run))
                        save(out_path, data)
                        write_summary(out_path, data)

                        verdict = review.get("Verdict", {}) if isinstance(review, dict) else {}
                        decision = verdict.get("Decision") or "?"
                        score = verdict.get("Overall Score")
                        score = score if score is not None else "?"
                        print(f"{tag} -> {decision} {score} ({secs}s)  [{len(completed)}/{total}]", flush=True)
                        if args.delay:
                            time.sleep(args.delay)
    except KeyboardInterrupt:
        print(f"\nInterrupted. {len(completed)}/{total} saved to {out_path}. "
              f"Re-run the same command to resume.", file=sys.stderr)
        sys.exit(130)

    print(f"\nDone: {len(completed)}/{total} reviews complete, {fail_count} failure(s) this run.")
    if len(completed) < total:
        print("Some slots are still missing — re-run the same command to retry them.")
    print(f"Results: {out_path}")
    print(f"Summary: {summary_path_for(out_path)}")


if __name__ == "__main__":
    main()
