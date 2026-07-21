#!/usr/bin/env python3
"""Automated workbook test harness for the art reviewer SDK.

Runs one full "workbook" for a single artwork: every experimental condition
(A–D) against each model, N runs each, and writes every review to a single
JSON file grouped by condition. Results are saved incrementally (after each
review), so a mid-run failure loses nothing and re-running resumes the
missing slots.

Conditions (what varies — see WORKBOOK.md) default to the A–E structure in
DEFAULT_CONDITIONS below, but a workbook TOML can define its own [[conditions]]
tables (key, label, and which inputs to send) so different workbook structures
— e.g. a pricing experiment where price is the varied input — run through the
same harness.

The condition is decided purely by which inputs the harness sends; it is
experiment metadata and is never injected into the prompt (that would bias
the model). Each output record is tagged with its condition, and each
condition bucket records its `send` list and the `inputs_used` values, which
the dashboard renders data-driven.

Usage:
    uv run python art_reviewer_sdk/run_workbook.py art_reviewer_sdk/workbooks/workbook.toml
    uv run python art_reviewer_sdk/run_workbook.py assets.toml --out results/x.json --runs 3 --delay 1
    uv run python art_reviewer_sdk/run_workbook.py --all   # sweep every artwork in the catalog

With --all, one workbook is run per entry in the catalog (artworks.json
beside the TOML, in file order), auto-numbering artwork_id TEST-001,
TEST-002, … and writing results/TEST-NNN.json for each. The TOML's
artwork/artwork_id keys are ignored; models, review_prompt, conditions and
--runs/--delay apply to every artwork. A failed artwork is skipped and
reported; re-running --all resumes each results file's missing slots.

The assets TOML provides one artwork's inputs:
    artwork       (optional catalog id — pulls the artwork's fields from
                   artworks.json beside the TOML; `catalog` overrides the
                   catalog path; TOML-set fields always win)
    artwork_path  (required unless `artwork` provides it; resolved relative
                   to whichever file defined it — TOML or catalog)
    description   (optional)
    models        (optional list of model IDs; default: MODELS below)
    [preferences] (optional table of named variants, e.g. related / unrelated;
                   conditions sending "preferences" run once per variant)
    [[conditions]] (optional list overriding the default A–E conditions)
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

# review puts review_prompts/ on sys.path so review_prompt_<N> modules import.
from review import review_image, load_instruction, MAX_IMAGE_EDGE  # noqa: E402  (path set above)

# Sampling knobs passed to every review. {} means provider defaults (the
# ART_REVIEWER_* env fallback is deliberately bypassed so a stray .env value
# can't silently change the experiment). Recorded in the results JSON.
KNOBS: dict = {}

# Default workbook assets file — used when no path is passed on the CLI.
DEFAULT_ASSETS = HERE / "workbooks" / "workbook.toml"

# Default models under test — exact API IDs. A workbook TOML can override
# with its own `models = [...]` list.
MODELS = ["gpt-5-mini", "gemini-3.5-flash", "gemini-3-flash-preview"]

# Transient-failure retries per review slot: total attempts, and the waits
# before the 2nd and 3rd attempt. Non-transient errors fail immediately.
MAX_ATTEMPTS = 3
RETRY_WAITS = (5, 20)
_TRANSIENT_TOKENS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED",
                     "500", "502", "504", "overloaded", "timeout", "timed out",
                     "Deadline", "Connection")


def is_transient(exc: Exception) -> bool:
    """Provider-agnostic check for retryable failures (capacity, rate limit,
    network) based on the error text — the three SDKs raise different types."""
    text = f"{type(exc).__name__}: {exc}"
    return any(t.lower() in text.lower() for t in _TRANSIENT_TOKENS)

# Inputs a condition may send to the model. "preferences" fans out: the
# condition runs once per [preferences] variant in the TOML. The others map
# to a single TOML value (see ASSET_KEY for the one differing key name).
SEND_FIELDS = ("description", "artist", "preferences", "price", "max_spend",
               "work_type", "media_note")
ASSET_KEY = {"price": "artwork_price"}  # send-field -> assets/TOML key

# The parts of a collector-preference profile JSON that are actually sent to
# the model. Identity/labelling fields (collectorName, profile) are dropped —
# a label like "AI Art Collector" biases the judgment far more than the taste
# data itself.
PROFILE_SEND_FIELDS = ("preferredMediums", "priorityRanking",
                       "collectorStatement", "favoriteArtistsOrWorks", "avoid")

# Default experimental conditions (A–E, see WORKBOOK.md). A workbook TOML can
# replace these with its own [[conditions]] tables — each needs a `key`, an
# optional `label`, and a `send` list drawn from SEND_FIELDS — so different
# workbook structures (e.g. pricing experiments) can vary whatever input is
# under test. In the defaults, price/max_spend/work_type ride along in every
# condition when present in the TOML (blank values are always omitted).
_BASE = ["price", "max_spend", "work_type", "media_note"]
DEFAULT_CONDITIONS = [
    {"key": "A", "label": "Artwork Only", "send": _BASE},
    {"key": "B", "label": "Artwork + Description", "send": ["description", *_BASE]},
    {"key": "C", "label": "Artwork + Artist Name", "send": ["artist", *_BASE]},
    {"key": "D", "label": "Artwork + Description + Artist Name",
     "send": ["description", "artist", *_BASE]},
    {"key": "E", "label": "Artwork + Description + Artist Name + Collector Preference",
     "send": ["description", "artist", "preferences", *_BASE]},
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# Artwork fields a catalog entry may provide (everything but the experiment
# knobs — models, review_prompt, conditions stay in the workbook TOML).
CATALOG_FIELDS = ("artwork_title", "artist", "work_type", "media_note",
                  "description", "artwork_price", "max_spend", "artwork_path",
                  "preferences")


def load_assets(path: Path, overrides: dict | None = None) -> dict:
    """Parse the per-workbook TOML and resolve the artwork path.

    The TOML can either define the artwork inline (artwork_path, description,
    …) or reference an entry in a JSON catalog via `artwork = "<id>"`
    (default catalog: artworks.json beside the TOML; override with `catalog`).
    Catalog fields fill in only where the TOML doesn't set the key itself —
    the TOML always wins, so one-off overrides need no catalog edit.

    `overrides` (used by --all) is applied on top of the parsed TOML before
    catalog resolution, so overridden keys behave as if set in the TOML.
    """
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        sys.exit(f"error: could not read assets file {path}: {exc}")
    if overrides:
        data.update(overrides)

    art_ref = str(data.get("artwork", "")).strip()
    data["artwork"] = art_ref  # recorded in the results for provenance
    path_base = path.parent  # what a relative artwork_path resolves against
    pref_base = path.parent  # what relative preference-profile paths resolve against
    if art_ref:
        catalog_path = path.parent / str(data.get("catalog", "artworks.json"))
        try:
            catalog = json.loads(catalog_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            sys.exit(f"error: could not read artwork catalog {catalog_path}: {exc}")
        entry = catalog.get(art_ref)
        if not isinstance(entry, dict):
            sys.exit(f"error: artwork '{art_ref}' not found in {catalog_path} — "
                     f"available: {', '.join(sorted(catalog))}")
        for key in CATALOG_FIELDS:
            if key not in data and key in entry:
                data[key] = entry[key]
                if key == "artwork_path":
                    path_base = catalog_path.parent
                elif key == "preferences":
                    pref_base = catalog_path.parent

    if "artwork_path" not in data:
        sys.exit(f"error: {path} is missing required key 'artwork_path' "
                 f"(set it inline or reference a catalog entry via 'artwork')")

    art = Path(str(data["artwork_path"]))
    if not art.is_absolute():
        art = (path_base / art).resolve()
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
    data["media_note"] = str(data.get("media_note", "")).strip()

    # System-prompt selection: review_prompt_<N>.py. Record the version and load
    # the actual INSTRUCTION text used for every review in this workbook.
    version = data.get("review_prompt", 1)
    data["review_prompt"] = version
    try:
        data["instruction"] = load_instruction(version)
    except ValueError as exc:
        sys.exit(f"error: {exc} — set 'review_prompt' in the workbook TOML to an "
                 f"existing variant (e.g. 1 or 2)")

    # Collector preferences: a [preferences] table of named variants. Any
    # condition whose `send` includes "preferences" is run once per entry. A
    # bare string is also accepted (treated as a single "default" variant).
    prefs = data.get("preferences", {})
    if isinstance(prefs, str):
        prefs = {"default": prefs} if prefs.strip() else {}
    elif isinstance(prefs, dict):
        prefs = {k: str(v).strip() for k, v in prefs.items() if str(v).strip()}
    else:
        prefs = {}

    # A variant value ending in .json is a path to a collector-preference
    # profile file (workbooks/collector-preferences/*.json), resolved relative
    # to whichever file defined it — catalog or TOML. A string profile is sent
    # verbatim. An object profile is filtered to PROFILE_SEND_FIELDS before
    # serializing — identity fields like collectorName stay out of the prompt
    # (a name like "AI Art Collector" is itself a heavy bias). The resolved
    # text is what gets recorded, plus the source path for provenance.
    data["preference_files"] = {}
    for name, val in list(prefs.items()):
        if not val.lower().endswith(".json"):
            continue
        p = Path(val)
        if not p.is_absolute():
            p = (pref_base / p).resolve()
        try:
            profile = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            sys.exit(f"error: could not read collector-preference profile for "
                     f"variant '{name}': {p}: {exc}")
        if isinstance(profile, dict):
            sent = {k: profile[k] for k in PROFILE_SEND_FIELDS if k in profile}
            if not sent:
                sys.exit(f"error: collector-preference profile {p} has none of "
                         f"the expected fields {list(PROFILE_SEND_FIELDS)}")
            text = json.dumps(sent, indent=2, ensure_ascii=False)
        else:
            text = str(profile).strip()
        if not text:
            sys.exit(f"error: collector-preference profile {p} is empty")
        prefs[name] = text
        data["preference_files"][name] = str(p)
    data["preferences"] = prefs

    # Models under test: optional `models` list overrides the MODELS default.
    models = data.get("models", MODELS)
    if (not isinstance(models, list) or not models
            or not all(isinstance(m, str) and m.strip() for m in models)):
        sys.exit(f"error: {path}: 'models' must be a non-empty list of model ID strings")
    models = [m.strip() for m in models]
    if len(set(models)) != len(models):
        sys.exit(f"error: {path}: 'models' contains duplicates")
    data["models"] = models

    # Experimental conditions: optional [[conditions]] tables override the
    # default A–E structure (so a workbook can vary e.g. pricing instead).
    raw = data.get("conditions", DEFAULT_CONDITIONS)
    if not isinstance(raw, list) or not raw:
        sys.exit(f"error: {path}: 'conditions' must be a non-empty [[conditions]] list")
    conds, seen = [], set()
    for i, c in enumerate(raw, 1):
        if not isinstance(c, dict) or not str(c.get("key", "")).strip():
            sys.exit(f"error: {path}: [[conditions]] entry {i} needs a 'key'")
        key = str(c["key"]).strip()
        if key in seen:
            sys.exit(f"error: {path}: duplicate condition key '{key}'")
        seen.add(key)
        send = c.get("send", [])
        if not isinstance(send, list):
            sys.exit(f"error: {path}: condition '{key}' 'send' must be a list")
        unknown = [f for f in send if f not in SEND_FIELDS]
        if unknown:
            sys.exit(f"error: {path}: condition '{key}' has unknown send field(s) "
                     f"{unknown} — valid: {list(SEND_FIELDS)}")
        conds.append({"key": key, "label": str(c.get("label", key)).strip() or key,
                      "send": [str(f) for f in send]})
    data["conditions"] = conds
    return data


def condition_inputs(cond: dict, assets: dict) -> dict:
    """The non-preference input values a condition sends, keyed by send-field
    name (blank values omitted — they are never sent to the model)."""
    return {
        f: assets[ASSET_KEY.get(f, f)]
        for f in cond["send"]
        if f != "preferences" and assets.get(ASSET_KEY.get(f, f))
    }


def build_skeleton(assets: dict, runs: int) -> dict:
    """Fresh output structure with empty per-condition review buckets."""
    conditions = {}
    for cond in assets["conditions"]:
        conditions[cond["key"]] = {
            "label": cond["label"],
            "send": list(cond["send"]),
            "inputs_used": condition_inputs(cond, assets),
            "preference_variants": (dict(assets["preferences"])
                                    if "preferences" in cond["send"] else {}),
            "preference_files": (dict(assets.get("preference_files", {}))
                                 if "preferences" in cond["send"] else {}),
            "reviews": [],
        }
    ts = now_iso()
    return {
        "workbook": {
            "artwork_id": assets["artwork_id"],
            "artwork": assets.get("artwork", ""),  # catalog id, if referenced
            "artwork_title": assets["artwork_title"],
            "artist": assets["artist"],
            "work_type": assets["work_type"],
            "media_note": assets["media_note"],
            "artwork_price": assets["artwork_price"],
            "max_spend": assets["max_spend"],
            "artwork_path": assets["artwork_path"],
            "models": list(assets["models"]),
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
    for cond in assets["conditions"]:
        valid[cond["key"]] = (set(assets["preferences"].keys())
                              if "preferences" in cond["send"] else {None})
    models = set(assets["models"])
    dropped = 0
    for cond in data["conditions"]:
        prior = existing.get("conditions", {}).get(cond, {}).get("reviews", [])
        # Drop prior reviews that don't match the current config — an unknown
        # preference variant (renamed/removed) or a model no longer in the
        # models list — so those slots get re-run rather than orphaned.
        # Reviews under condition keys that no longer exist are dropped too.
        kept = [r for r in prior
                if r.get("preference_variant") in valid[cond]
                and r.get("model") in models]
        dropped += len(prior) - len(kept)
        data["conditions"][cond]["reviews"] = kept
    if dropped:
        print(f"WARNING: dropped {dropped} prior review(s) whose model or "
              f"preference variant is not in the current config — they will "
              f"be re-run. Use a fresh --out to keep the old arm intact.",
              file=sys.stderr)
    return data


def completed_slots(data: dict) -> set:
    """Set of (condition, preference_variant, model, run) tuples recorded."""
    done = set()
    for cond, bucket in data["conditions"].items():
        for r in bucket.get("reviews", []):
            done.add((cond, r.get("preference_variant"), r.get("model"), r.get("run")))
    return done


def total_slots(assets: dict, runs: int) -> int:
    """Planned review count: models×runs per condition, ×variants for
    conditions that send preferences."""
    t = 0
    for cond in assets["conditions"]:
        nvar = len(assets["preferences"]) if "preferences" in cond["send"] else 1
        t += nvar * len(assets["models"]) * runs
    return t


def save(out_path: Path, data: dict) -> None:
    """Atomically write the whole results structure (temp file + os.replace)."""
    data["workbook"]["updated_at"] = now_iso()
    model_index = {m: i for i, m in enumerate(data["workbook"].get("models", []))}
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
    model_index = {m: i for i, m in enumerate(data["workbook"].get("models", []))}
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


def run_workbook(assets: dict, out_path: Path, runs: int, delay: float,
                 label_fallback: str = "") -> tuple[int, int]:
    """Run one artwork's full workbook (all conditions × models × runs),
    saving incrementally to out_path. Returns (completed, total). Raises
    KeyboardInterrupt through to the caller after printing resume info."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = load_or_init(out_path, assets, runs)
    completed = completed_slots(data)
    write_summary(out_path, data)  # keep the summary present/current even on a no-op resume

    image_bytes = Path(assets["artwork_path"]).read_bytes()
    mime = mimetypes.guess_type(assets["artwork_path"])[0] or "image/jpeg"

    n_variants = len(assets["preferences"])
    total = total_slots(assets, runs)
    fail_count = 0

    cond_keys = [c["key"] for c in assets["conditions"]]
    pref_conds = [c["key"] for c in assets["conditions"] if "preferences" in c["send"]]
    label = assets["artwork_id"] or assets["artwork_title"] or label_fallback
    print(f"Workbook: {label}  ({total} reviews — conditions {', '.join(cond_keys)} "
          f"× {len(assets['models'])} models × {runs} runs"
          + (f"; {'/'.join(pref_conds)} ×{n_variants} preference variant"
             f"{'' if n_variants == 1 else 's'}" if pref_conds else "") + ")")
    if pref_conds and not n_variants:
        print(f"NOTE: no [preferences] entries found — condition(s) "
              f"{', '.join(pref_conds)} will be skipped.", file=sys.stderr)
    if completed:
        print(f"Resuming — {len(completed)}/{total} already complete.")
    print(f"Output: {out_path}\n")

    try:
        for cond_cfg in assets["conditions"]:
            cond = cond_cfg["key"]
            bucket = data["conditions"][cond]
            inputs = condition_inputs(cond_cfg, assets)
            use_p = "preferences" in cond_cfg["send"]
            variants = list(assets["preferences"].items()) if use_p else [(None, "")]
            for variant, pref in variants:
                for model in assets["models"]:
                    for run in range(1, runs + 1):
                        if (cond, variant, model, run) in completed:
                            continue
                        vtag = f"/{variant}" if variant else ""
                        tag = f"[{cond}{vtag}][{model}] run {run}/{runs}"
                        t0 = time.time()
                        review = None
                        for attempt in range(1, MAX_ATTEMPTS + 1):
                            try:
                                review = review_image(
                                    model, image_bytes, mime,
                                    knobs=KNOBS, preferences=pref,
                                    description=inputs.get("description", ""),
                                    artist=inputs.get("artist", ""),
                                    price=inputs.get("price", ""),
                                    work_type=inputs.get("work_type", ""),
                                    media_note=inputs.get("media_note", ""),
                                    max_spend=inputs.get("max_spend", ""),
                                    instruction=assets["instruction"],
                                )
                                break
                            except Exception as exc:
                                if attempt < MAX_ATTEMPTS and is_transient(exc):
                                    wait = RETRY_WAITS[attempt - 1]
                                    print(f"[retry] {tag} attempt {attempt} -> "
                                          f"{type(exc).__name__}: {exc} — retrying in {wait}s",
                                          file=sys.stderr, flush=True)
                                    time.sleep(wait)
                                    continue
                                fail_count += 1
                                print(f"[FAIL] {tag} -> {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                                break
                        if review is None:
                            if delay:
                                time.sleep(delay)
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
                        if delay:
                            time.sleep(delay)
    except KeyboardInterrupt:
        print(f"\nInterrupted. {len(completed)}/{total} saved to {out_path}. "
              f"Re-run the same command to resume.", file=sys.stderr)
        raise

    print(f"\nDone: {len(completed)}/{total} reviews complete, {fail_count} failure(s) this run.")
    if len(completed) < total:
        print("Some slots are still missing — re-run the same command to retry them.")
    print(f"Results: {out_path}")
    print(f"Summary: {summary_path_for(out_path)}")
    return len(completed), total


def run_all(toml_path: Path, runs: int, delay: float) -> None:
    """Sweep mode (--all): run one workbook per catalog entry, in catalog
    order, auto-numbering artwork_id TEST-001, TEST-002, … A failed artwork
    is logged and skipped; re-running resumes each results file."""
    try:
        with open(toml_path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        sys.exit(f"error: could not read assets file {toml_path}: {exc}")

    inline = [k for k in CATALOG_FIELDS if k in raw]
    if inline:
        print(f"WARNING: {toml_path} sets artwork field(s) {inline} inline — "
              f"with --all these override the catalog for EVERY artwork.",
              file=sys.stderr)

    catalog_path = toml_path.parent / str(raw.get("catalog", "artworks.json"))
    try:
        catalog = json.loads(catalog_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        sys.exit(f"error: could not read artwork catalog {catalog_path}: {exc}")
    if not isinstance(catalog, dict) or not catalog:
        sys.exit(f"error: artwork catalog {catalog_path} is empty or not a JSON object")

    keys = list(catalog)  # file order — keeps TEST-NNN ids stable across runs
    print(f"Sweep: {len(keys)} artworks from {catalog_path} "
          f"(TEST-001 … TEST-{len(keys):03d})\n")

    results = []  # (artwork_id, key, completed, total) or (artwork_id, key, None, reason)
    for i, key in enumerate(keys, 1):
        artwork_id = f"TEST-{i:03d}"
        print(f"=== [{i}/{len(keys)}] {artwork_id}: {key} ===")
        try:
            assets = load_assets(toml_path, overrides={"artwork": key,
                                                       "artwork_id": artwork_id})
            out_path = REPO_ROOT / "results" / f"{artwork_id}.json"
            done, total = run_workbook(assets, out_path, runs, delay,
                                       label_fallback=toml_path.stem)
            results.append((artwork_id, key, done, total))
        except KeyboardInterrupt:
            print(f"\nSweep interrupted at {artwork_id} ({key}). "
                  f"Re-run with --all to resume.", file=sys.stderr)
            sys.exit(130)
        except SystemExit as exc:
            print(f"[SKIP] {artwork_id} ({key}): {exc}", file=sys.stderr, flush=True)
            results.append((artwork_id, key, None, str(exc)))
        except Exception as exc:
            print(f"[SKIP] {artwork_id} ({key}): {type(exc).__name__}: {exc}",
                  file=sys.stderr, flush=True)
            results.append((artwork_id, key, None, str(exc)))
        print()

    print("=== Sweep summary ===")
    incomplete = 0
    for artwork_id, key, done, total in results:
        if done is None:
            print(f"{artwork_id}  {key}: SKIPPED ({total})")
            incomplete += 1
        else:
            print(f"{artwork_id}  {key}: {done}/{total}")
            if done < total:
                incomplete += 1
    if incomplete:
        print(f"\n{incomplete} artwork(s) incomplete — re-run with --all to "
              f"resume the missing slots.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a full art-reviewer workbook.")
    parser.add_argument("assets", nargs="?", type=Path, default=DEFAULT_ASSETS,
                        help="path to the workbook TOML assets file (default: %(default)s)")
    parser.add_argument("--all", action="store_true", dest="run_all",
                        help="run every artwork in the catalog (artworks.json beside "
                             "the TOML), auto-numbering artwork_id TEST-001, TEST-002, …")
    parser.add_argument("--out", type=Path, default=None,
                        help="results JSON path (default: results/<artwork_id-or-stem>.json)")
    parser.add_argument("--runs", type=int, default=3, help="runs per condition per model (default: 3)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds to pause between calls (default: 0)")
    args = parser.parse_args()

    if args.run_all:
        if args.out is not None:
            parser.error("--out cannot be used with --all (each artwork gets its "
                         "own results/TEST-NNN.json)")
        run_all(args.assets, args.runs, args.delay)
        return

    assets = load_assets(args.assets)

    if args.out is not None:
        out_path = args.out
    else:
        stem = assets["artwork_id"] or args.assets.stem
        out_path = REPO_ROOT / "results" / f"{stem}.json"

    try:
        run_workbook(assets, out_path, args.runs, args.delay,
                     label_fallback=args.assets.stem)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
