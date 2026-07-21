#!/usr/bin/env python3
"""LLM-ready data export of the cross-experiment study.

Distills results/experiment-*/ (raw JSON is far too large to hand to a chat
model) into a whitepaper_export/ bundle sized for a single conversation:

    README.md       what the bundle is and how the files key together
    metadata.md     study design: experiments, conditions, full system
                    prompts, collector-preference profiles, artwork catalog
    aggregates.md   precomputed stats tables (means, ACQUIRE rates, ...)
    reviews.csv     one numeric row per review (no prose)
    rationales.csv  the verdict-rationale text per review

Reuses the loading layer from compare_dashboards.py; reads results only.

Usage:
    uv run python art_reviewer_sdk/export_whitepaper.py [--out DIR]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from compare_dashboards import discover_experiments, load_all  # noqa: E402
from dashboard import DIMS  # noqa: E402

REVIEW_COLS = ["experiment", "review_prompt", "artwork_id", "artwork_title",
               "condition", "preference_variant", "model", "run",
               *DIMS, "overall", "decision", "is_error"]
RATIONALE_COLS = ["experiment", "artwork_id", "condition", "preference_variant",
                  "model", "run", "decision", "overall", "rational"]


def md_table(df: pd.DataFrame, floatfmt: str = "{:.1f}") -> str:
    """Small dependency-free markdown table (to_markdown would need tabulate)."""
    def cell(v):
        if isinstance(v, float):
            return "" if pd.isna(v) else floatfmt.format(v)
        return str(v)
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(cell(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def load_reference_jsons(experiments: list[dict]) -> tuple[dict, dict, dict]:
    """From the raw JSONs: {exp_name: first workbook block},
    {exp_name: conditions block of the first file}, and the artwork catalog
    {artwork_id: fields} from every file of the first experiment."""
    workbooks, conditions, catalog = {}, {}, {}
    for exp in experiments:
        data = json.loads(exp["files"][0].read_text())
        workbooks[exp["name"]] = data.get("workbook", {})
        conditions[exp["name"]] = data.get("conditions", {})
    for f in experiments[0]["files"]:
        wb = json.loads(f.read_text()).get("workbook", {})
        aid = wb.get("artwork_id") or f.stem
        catalog[aid] = wb
    return workbooks, conditions, catalog


def metadata_md(experiments: list[dict], workbooks: dict, conditions: dict,
                catalog: dict) -> str:
    parts = ["# Study design\n"]

    rows = []
    for e in experiments:
        wb = workbooks[e["name"]]
        rows.append({
            "experiment": e["name"],
            "models": " + ".join(e["models"]),
            "system prompt": f"v{e['prompt']}",
            "runs/condition": wb.get("runs_per_condition", ""),
            "sampling knobs": json.dumps(wb.get("sampling_knobs", {})) or "{}",
            "max image edge": wb.get("max_image_edge", ""),
            "started": str(wb.get("started_at", ""))[:10],
        })
    parts.append("## Experiments\n")
    parts.append("The study is a 2×2 design: model set × system-prompt version. "
                 "Every experiment reviewed the same artworks under the same "
                 "conditions.\n")
    parts.append(md_table(pd.DataFrame(rows)))

    parts.append("\n\n## Experimental conditions\n")
    parts.append("The condition determines which inputs are sent with the "
                 "artwork image; it is never named in the prompt itself. "
                 "Conditions that send `preferences` run once per collector-"
                 "preference variant.\n")
    ref_exp = experiments[0]["name"]
    crows = []
    for key, bucket in conditions[ref_exp].items():
        crows.append({
            "condition": key,
            "label": bucket.get("label", key),
            "inputs sent": ", ".join(bucket.get("send", [])) or "(image only)",
            "preference variants": ", ".join(bucket.get("preference_variants", {}))
                                   or "—",
        })
    parts.append(md_table(pd.DataFrame(crows)))
    for name, exp_conditions in conditions.items():
        if list(exp_conditions) != list(conditions[ref_exp]):
            parts.append(f"\nNOTE: {name} uses a different condition structure: "
                         f"{list(exp_conditions)}")

    parts.append("\n\n## Collector-preference profiles\n")
    parts.append("Sent verbatim (as JSON) in conditions that include "
                 "`preferences`. `related` aligns with the tested art; "
                 "`unrelated` does not.\n")
    seen = set()
    for exp_conditions in conditions.values():
        for bucket in exp_conditions.values():
            for variant, text in bucket.get("preference_variants", {}).items():
                if variant not in seen:
                    seen.add(variant)
                    parts.append(f"\n### Variant: {variant}\n\n```\n{text}\n```")

    parts.append("\n\n## System prompts\n")
    parts.append("The full reviewer system prompt used by each experiment "
                 "(the v4 → v5 change is one of the two study factors).\n")
    by_version = {}
    for e in experiments:
        by_version.setdefault(e["prompt"], workbooks[e["name"]].get("system_prompt", ""))
    for version, text in sorted(by_version.items(), key=lambda kv: str(kv[0])):
        used_by = ", ".join(e["name"] for e in experiments if e["prompt"] == version)
        parts.append(f"\n### Prompt v{version} (used by {used_by})\n\n```\n{text}\n```")

    parts.append("\n\n## Artwork catalog\n")
    arows = []
    for aid in sorted(catalog):
        wb = catalog[aid]
        arows.append({
            "artwork_id": aid,
            "title": wb.get("artwork_title", ""),
            "artist": wb.get("artist", ""),
            "work type": wb.get("work_type", "") or "—",
            "media note": wb.get("media_note", "") or "—",
        })
    parts.append(md_table(pd.DataFrame(arows)))
    return "\n".join(parts) + "\n"


def aggregates_md(df: pd.DataFrame, experiments: list[dict]) -> str:
    valid = df[~df["is_error"] & df["overall"].notna()]

    def acq(d):
        return 100.0 * (d == "ACQUIRE").mean()

    parts = ["# Precomputed aggregates\n",
             "All tables exclude error/refusal reviews (error counts are in "
             "the first table). Scores are the 0-100 holistic Overall Score; "
             "ACQUIRE is the percent of reviews deciding ACQUIRE. Everything "
             "here can be recomputed from reviews.csv.\n"]

    exp_means = valid.groupby("experiment", observed=True)["overall"].mean()
    headline = "; ".join(f"{k} {v:.1f}" for k, v in exp_means.items())
    parts.append(f"Headline mean overall score per experiment: {headline}.\n")

    g = valid.groupby(["experiment", "model"], observed=True)
    t1 = g.agg(reviews=("overall", "size"), mean_overall=("overall", "mean"),
               std_overall=("overall", "std"),
               acquire_pct=("decision", acq)).reset_index()
    errs = (df.groupby(["experiment", "model"], observed=True)["is_error"]
              .sum().reset_index(name="errors"))
    t1 = t1.merge(errs, on=["experiment", "model"])
    parts.append("\n## Per experiment × model\n")
    parts.append(md_table(t1))

    t2 = (valid.groupby(["experiment", "model", "cond_pref"], observed=True)
               .agg(mean_overall=("overall", "mean"),
                    acquire_pct=("decision", acq)).reset_index()
               .rename(columns={"cond_pref": "condition"}))
    parts.append("\n\n## Per experiment × model × condition\n")
    parts.append(md_table(t2))

    t3 = (valid.groupby(["experiment", "model"], observed=True)[DIMS]
               .mean().reset_index())
    parts.append("\n\n## Mean dimension scores (1-10) per experiment × model\n")
    parts.append(md_table(t3))

    t4 = (valid.groupby(["artwork_id", "experiment"], observed=True)["overall"]
               .mean().unstack("experiment")
               .reindex(columns=[e["name"] for e in experiments]).reset_index())
    parts.append("\n\n## Mean overall score per artwork × experiment\n")
    parts.append(md_table(t4))
    return "\n".join(parts) + "\n"


def figures_md(experiments: list[dict], df: pd.DataFrame) -> str:
    """Manifest of the charts the user can screenshot on request — so a
    whitepaper agent (which cannot render the HTML dashboards) knows exactly
    which figure to ask for by name."""
    n_art = df["artwork_id"].nunique()
    exps = ", ".join(e["name"] for e in experiments)
    return f"""# Available figures (screenshots on request)

You (the writing agent) cannot open the interactive dashboards, but the user
can screenshot any chart below and paste it into this conversation. When a
section of the paper needs a figure, ask the user for it **by the exact name
below** (plus the artwork id where applicable). You can also regenerate any
of these yourself from reviews.csv if you have a code-execution tool.

## From the comparison dashboard (dashboards/compare.html)

Series coloring: one hue per experiment; darker shade = the GPT model,
lighter shade = the Gemini model.

- **Experiments summary table** — per experiment × model: reviews, errors,
  mean overall, ACQUIRE rate. (Overview, top.)
- **Mean overall score — condition × experiment · model** — grouped bars,
  A-E on the x-axis, one bar per experiment·model, with run spread.
  (Overview.)
- **ACQUIRE rate — condition × experiment · model** — same layout, percent
  deciding ACQUIRE. (Overview.)
- **Mean overall score — artwork × experiment · model** — {n_art}-row heatmap,
  red-to-green 0-100. (Overview, bottom.)
- **Per-artwork condition bars** — "<artwork_id> — mean overall score by
  condition": the 8 experiment·model series across A-E for one artwork.
  (Pick the artwork in the top strip; name the artwork_id when requesting.)
- **Per-artwork verdict map** — "<artwork_id> — majority verdict per
  condition": green/red/amber grid (ACQUIRE/PASS/split) with mean scores,
  experiment·model rows × condition columns. (Same picker.)

## From the per-experiment dashboards (results/<experiment>/index.html)

Available for each of: {exps}. One artwork at a time (thumbnail picker):
score-summary heatmap, overall score by condition, per-dimension score
spreads, ACQUIRE/PASS split, run-to-run drift, preference-variant effect,
and a browsable list of every verdict + rationale.

## Requesting a figure

Ask like: "Please screenshot **Mean overall score — condition × experiment ·
model** from the comparison dashboard" or "Please screenshot the
**per-artwork verdict map for TEST-001**." The user will paste the image;
then reference it in the draft as a numbered figure with your caption.
"""


def readme_md(experiments: list[dict], df: pd.DataFrame) -> str:
    exps = "\n".join(f"- {e['label']}" for e in experiments)
    return f"""# Art-reviewer study — data bundle

Generated {datetime.now().astimezone().isoformat(timespec='seconds')} from
results/experiment-*/. An autonomous "art reviewer" agent (an LLM given a
structured review rubric) reviewed {df['artwork_id'].nunique()} artworks and
decided ACQUIRE or PASS for each. The study varies two factors (2×2):
the model set and the system-prompt version (v4 = directive, with taste/
scoring rules; v5 = minimal, structure only):

{exps}

Each artwork was reviewed under every experimental condition (A-E: which
contextual inputs accompany the image — see metadata.md), {df['run'].max():.0f} runs per
condition per model. Total reviews: {len(df)}.

## Files

- **metadata.md** — study design: experiments, condition definitions, the
  full system-prompt texts, collector-preference profiles, artwork catalog.
- **aggregates.md** — precomputed stats tables (recomputable from reviews.csv).
- **reviews.csv** — one row per review ({len(df)} rows), numeric only:
  dimension scores (1-10), overall score (0-100), decision.
- **rationales.csv** — the model's 2-3 sentence verdict rationale for every
  review (for qualitative quotes).
- **figures.md** — the charts the user can screenshot for you on request;
  ask for them by name when the paper needs a figure.

Rows across the CSVs key on (experiment, artwork_id, condition,
preference_variant, model, run). `preference_variant` is empty except in
conditions that send collector preferences. `is_error` marks refusals or
malformed reviews — exclude them from numeric analysis.
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export an LLM-ready whitepaper data bundle from "
                    "results/experiment-*/.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "whitepaper_export",
                        help="output directory (default: %(default)s)")
    args = parser.parse_args()

    experiments = discover_experiments(REPO_ROOT / "results")
    if not experiments:
        sys.exit("error: no results/experiment-*/ directories found.")
    df, _ = load_all(experiments)
    workbooks, conditions, catalog = load_reference_jsons(experiments)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    df = df.copy()
    df["review_prompt"] = df["experiment"].map(
        {e["name"]: e["prompt"] for e in experiments})
    df["preference_variant"] = df["preference_variant"].replace("none", "")
    df = df.sort_values(["experiment", "artwork_id", "condition",
                         "preference_variant", "model", "run"])

    df[REVIEW_COLS].to_csv(out / "reviews.csv", index=False)
    df[RATIONALE_COLS].to_csv(out / "rationales.csv", index=False)
    (out / "metadata.md").write_text(
        metadata_md(experiments, workbooks, conditions, catalog))
    (out / "aggregates.md").write_text(aggregates_md(df, experiments))
    (out / "figures.md").write_text(figures_md(experiments, df))
    (out / "README.md").write_text(readme_md(experiments, df))

    for f in sorted(out.iterdir()):
        print(f"  {f.relative_to(REPO_ROOT)}  ({f.stat().st_size / 1024:.0f} KB)")
    print(f"Bundle written to {out}  ({len(df)} reviews, "
          f"{len(experiments)} experiments)")


if __name__ == "__main__":
    main()
