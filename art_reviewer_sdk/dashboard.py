#!/usr/bin/env python3
"""Combined visual dashboard for all workbook results.

Scans every results/*.json produced by run_workbook.py and builds ONE
self-contained, interactive HTML page (Plotly) at dashboards/index.html, with a
dropdown at the top to switch between tests. Each workbook section shows the
artwork + condition key, summary heatmap, score spreads, ACQUIRE/PASS split,
run-to-run drift, the preference effect, and a Verdicts & Rationales browser
(every review's rationale, expandable to the full critique). Re-run after any
new workbook to fold it into the page.

Usage:
    uv run python art_reviewer_sdk/dashboard.py            # rebuild dashboards/index.html
    uv run python art_reviewer_sdk/dashboard.py --open     # ...and open it
    uv run python art_reviewer_sdk/dashboard.py --offline  # inline Plotly.js (no internet)
"""

import argparse
import base64
import html
import io
import json
import sys
import textwrap
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.offline

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from review import DIMENSIONS  # noqa: E402  five dimension names — single source of truth

DIMS = list(DIMENSIONS)
# Fallback condition order for frames without the ordered categorical set by
# flatten(); the real order always comes from the results file itself.
COND_ORDER = ["A", "B", "C", "D", "E"]
PALETTE = px.colors.qualitative.Set2
DECISION_COLORS = {"ACQUIRE": "#2e9e5b", "PASS": "#c2453f"}


def flatten(data: dict) -> pd.DataFrame:
    """One row per review, with dimension scores, overall, decision, is_error."""
    rows = []
    for cond, bucket in data.get("conditions", {}).items():
        label = bucket.get("label", cond)
        for r in bucket.get("reviews", []):
            # Be defensive: a model can return a malformed/truncated review where
            # Evaluation is a string, Verdict is missing, or a dimension isn't an
            # object. Coerce anything unexpected so it lands as an error row.
            review = r.get("review")
            review = review if isinstance(review, dict) else {}
            ev = review.get("Evaluation")
            ev = ev if isinstance(ev, dict) else {}
            verdict = review.get("Verdict")
            verdict = verdict if isinstance(verdict, dict) else {}
            decision = (verdict.get("Decision") or "").strip().upper()
            overall = verdict.get("Overall Score")
            rational = (verdict.get("Rational") or "").strip()
            row = {
                "condition": cond,
                "condition_label": label,
                "model": r.get("model"),
                "preference_variant": r.get("preference_variant") or "none",
                "run": r.get("run"),
                "overall": overall,
                "decision": decision,
                # A refusal/error/malformed stub has a blank decision.
                "is_error": decision not in ("ACQUIRE", "PASS")
                or (overall in (0, None) and not rational),
                "rational": rational,
                # Full review object, carried through for the rationale
                # browser (never enters numeric aggregation).
                "review_obj": review,
            }
            for dim in DIMS:
                dv = ev.get(dim)
                row[dim] = dv.get("Score") if isinstance(dv, dict) else None
            rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for col in ["overall", "run", *DIMS]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Condition order is whatever the results file defines (its conditions
    # dict is insertion-ordered) — workbooks may use structures other than A–E.
    df["condition"] = pd.Categorical(
        df["condition"], categories=list(data.get("conditions", {})), ordered=True)
    return df


def with_cond_pref(v):
    """Add a `cond_pref` column: condition for A/B, condition·variant for C/D —
    so the two preferences in C and D are never pooled into one group."""
    vv = v.copy()
    vv["cond_pref"] = [
        c if pv == "none" else f"{c} · {pv}"
        for c, pv in zip(vv["condition"], vv["preference_variant"])
    ]
    return vv


def cond_order_of(v) -> list:
    """The workbook's condition order — from the ordered categorical set by
    flatten(), falling back to the classic A–E for plain frames."""
    col = v["condition"]
    if isinstance(col.dtype, pd.CategoricalDtype):
        return list(col.cat.categories)
    return COND_ORDER


def cond_pref_order(v):
    """Ordered cond_pref categories: plain conditions first as-is, preference
    conditions split into one entry per variant."""
    order = []
    for c in cond_order_of(v):
        for pv in sorted(v.loc[v["condition"] == c, "preference_variant"].unique()):
            order.append(c if pv == "none" else f"{c} · {pv}")
    return order


def _clean_facet_titles(fig):
    """Strip the "col=" prefix Plotly adds to facet titles."""
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


# ---- individual figures (return None when there's nothing to plot) ----

def _wrap_hover(text: str, width: int = 60, max_lines: int = 4) -> str:
    """Wrap free text into <br>-joined lines for a Plotly tooltip, capped so
    a long rationale can't cover the whole plot."""
    lines = textwrap.wrap(str(text or ""), width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] += " …"
    return "<br>".join(lines)


def fig_overall_by_condition(v, models, cmap):
    if v.empty:
        return None
    vv = with_cond_pref(v)
    vv["hover_rational"] = [_wrap_hover(t) for t in vv["rational"]]
    fig = px.box(vv, x="cond_pref", y="overall", color="model", points="all",
                 category_orders={"cond_pref": cond_pref_order(v), "model": models},
                 color_discrete_map=cmap, boxmode="group",
                 custom_data=["run", "decision", "hover_rational"],
                 title="Overall Score by Condition & Preference (context effect)")
    fig.update_traces(hovertemplate=(
        "%{x} — run %{customdata[0]}<br>"
        "overall %{y} — %{customdata[1]}<br>"
        "<i>%{customdata[2]}</i>"
        "<extra>%{fullData.name}</extra>"))
    fig.update_layout(yaxis_range=[0, 100], xaxis_title="condition · preference")
    return fig


def fig_dimensions(v, models, cmap):
    if v.empty:
        return None
    long = v.melt(id_vars=["model", "decision", "run"], value_vars=DIMS,
                  var_name="dimension", value_name="score").dropna(subset=["score"])
    if long.empty:
        return None
    fig = px.box(long, x="dimension", y="score", color="model", points="all",
                 category_orders={"dimension": DIMS, "model": models},
                 color_discrete_map=cmap, boxmode="group",
                 hover_data=["decision", "run"],
                 title="Evaluation Dimension Scores by Model")
    fig.update_layout(yaxis_range=[0, 10])
    return fig


def fig_decision_split(v, models):
    """One panel per model; within each, a stacked ACQUIRE (green) / PASS (red)
    bar for every condition·preference group. Bar height = number of runs."""
    if v.empty:
        return None
    vv = with_cond_pref(v)
    order = cond_pref_order(v)
    grp = vv.groupby(["cond_pref", "model", "decision"]).size().reset_index(name="runs")
    if grp.empty:
        return None
    fig = px.bar(grp, x="cond_pref", y="runs", color="decision",
                 facet_col="model", barmode="stack",
                 category_orders={"cond_pref": order, "model": models,
                                  "decision": ["ACQUIRE", "PASS"]},
                 color_discrete_map=DECISION_COLORS,
                 title="Decision Split per Model (ACQUIRE vs PASS by condition · preference)")
    fig.update_layout(yaxis_title="# runs", legend_title_text="decision")
    fig.update_yaxes(dtick=1)  # run counts are integers
    fig.update_xaxes(tickangle=-40, title_text="")
    return _clean_facet_titles(fig)


def fig_preference(v, models, cmap):
    cd = v[v["preference_variant"] != "none"]
    if cd.empty:
        return None
    fig = px.box(cd, x="preference_variant", y="overall", color="model", points="all",
                 facet_col="condition", category_orders={"model": models},
                 color_discrete_map=cmap, boxmode="group",
                 title="Preference Effect on Overall Score")
    fig.update_layout(yaxis_range=[0, 100])
    return _clean_facet_titles(fig)


def fig_run_drift(v, models, cmap):
    vv = with_cond_pref(v).dropna(subset=["overall", "run"]).sort_values("run")
    if vv.empty:
        return None
    # Lines connect a model's three runs within each condition·preference facet.
    fig = px.line(vv, x="run", y="overall", color="model", facet_col="cond_pref",
                  markers=True, hover_data=["decision"],
                  category_orders={"cond_pref": cond_pref_order(v), "model": models},
                  color_discrete_map=cmap, title="Overall Score Across Runs (consistency)")
    fig.update_layout(yaxis_range=[0, 100])
    fig.update_xaxes(dtick=1, tick0=1)
    return _clean_facet_titles(fig)


def fig_summary_heatmap(v, models):
    """Visual summary table: rows = models, columns = Overall, the five
    dimensions, and ACQUIRE rate. Cell text is the true value; color is each
    cell as a % of its metric's max (so the differently-scaled columns stay
    visually comparable)."""
    if v.empty:
        return None
    metrics = ["Overall", *DIMS, "ACQUIRE rate"]
    maxes = {"Overall": 100, "ACQUIRE rate": 100, **{d: 10 for d in DIMS}}
    ys, z, text = [], [], []
    for m in models:
        sub = v[v["model"] == m]
        if sub.empty:
            continue
        ys.append(m)
        zrow, trow = [], []
        for metric in metrics:
            if metric == "Overall":
                val = sub["overall"].mean()
                trow.append(f"{val:.0f}" if pd.notna(val) else "")
            elif metric == "ACQUIRE rate":
                val = (sub["decision"] == "ACQUIRE").mean() * 100
                trow.append(f"{val:.0f}%")
            else:
                val = sub[metric].mean()
                trow.append(f"{val:.1f}" if pd.notna(val) else "")
            zrow.append(val / maxes[metric] if pd.notna(val) else None)
        z.append(zrow)
        text.append(trow)
    if not ys:
        return None
    fig = go.Figure(go.Heatmap(
        z=z, x=metrics, y=ys, text=text, texttemplate="%{text}",
        textfont=dict(size=13), colorscale="RdYlGn", zmin=0, zmax=1,
        colorbar=dict(title="% of max", tickformat=".0%"),
        hovertemplate="%{y}<br>%{x}: %{text} (%{z:.0%} of max)<extra></extra>"))
    fig.update_layout(title="Model Summary — Overall, dimension means & ACQUIRE rate")
    fig.update_yaxes(autorange="reversed")  # first model on top
    return fig


# ---- HTML assembly ----

CSS = """
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 24px; background: #fafafa; color: #1a1a1a; }
  h1 { margin: 0 0 4px; font-size: 22px; }
  .meta { color: #666; font-size: 13px; margin-bottom: 20px; line-height: 1.5; }
  .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 18px; }
  .card { background: #fff; border: 1px solid #e6e6e6; border-radius: 10px;
          padding: 8px; overflow: hidden; }
  .wide { grid-column: 1 / -1; }
  .condkey { font-size: 13px; line-height: 1.55; color: #333; padding: 6px 10px; }
  .condkey h2 { font-size: 15px; margin: 2px 0 8px; }
  .condkey ul { margin: 0 0 10px; padding-left: 20px; }
  .condkey .ctx { margin: 4px 0; color: #555; }
  .condkey .ctx b { color: #1a1a1a; }
  .topbar { position: sticky; top: 0; z-index: 5; background: #fafafa;
            display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
            padding: 6px 0 10px; margin-bottom: 12px; border-bottom: 1px solid #e6e6e6; }
  .topbar h1 { margin: 0; font-size: 20px; white-space: nowrap; }
  .picker-bar { display: flex; gap: 10px; overflow-x: auto; padding: 2px; flex: 1; }
  .pick { display: flex; flex-direction: column; align-items: center; gap: 3px;
          border: 2px solid transparent; border-radius: 8px; background: #fff;
          padding: 5px; cursor: pointer; min-width: 86px; font: inherit; }
  .pick:hover { background: #f0f2f5; }
  .pick.active { border-color: #2e9e5b; background: #eefaf1; }
  .pick img, .pick .noimg { width: 72px; height: 72px; object-fit: cover;
          border-radius: 6px; border: 1px solid #ddd; display: block; background: #eee; }
  .pick .pid { font-size: 11px; font-weight: 600; color: #222; }
  .pick .pttl { font-size: 10px; color: #666; max-width: 84px; overflow: hidden;
          text-overflow: ellipsis; white-space: nowrap; }
  .wbtitle { margin: 0 0 4px; font-size: 18px; }
  section.wb[hidden] { display: none; }
  .errnote { color: #c2453f; }
  .wbhead { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;
            padding: 8px; }
  .wbhead img.wbart { max-width: 340px; max-height: 340px; width: auto; height: auto;
            border-radius: 8px; border: 1px solid #ddd; flex-shrink: 0; }
  .wbhead .condkey { flex: 1; min-width: 260px; }
  .decsum { font-size: 13px; padding: 10px 14px; height: 100%;
            box-sizing: border-box; display: flex; flex-direction: column; }
  .decsum h2 { font-size: 15px; margin: 2px 0 4px; }
  .decsum .dnote { display: block; font-size: 11px; font-weight: 400; color: #999;
                   margin-top: 2px; }
  .decsum { overflow-x: auto; }  /* many-model tables scroll instead of clipping */
  .decsum table { border-collapse: collapse; width: 100%; flex: 1; margin-top: 6px; }
  .decsum thead th { text-align: left; font-weight: 600; color: #555;
               padding: 6px 12px 6px 0; font-size: 12px; white-space: nowrap; }
  .decsum tbody th { text-align: left; font-weight: 600; color: #555;
               padding: 6px 12px 6px 0; font-size: 12px; white-space: nowrap;
               width: 1%; }
  .decsum tbody tr { border-top: 1px solid #f0f0f0; }
  .decsum td { padding: 6px 12px 6px 0; white-space: nowrap; }
  .dchip { display: inline-block; min-width: 30px; text-align: center;
           border: 0; border-radius: 6px; padding: 3px 7px; margin-right: 5px;
           font: inherit; font-size: 13px; font-weight: 600; color: #fff;
           cursor: pointer; font-variant-numeric: tabular-nums; }
  .dchip:hover { filter: brightness(1.12); }
  .dchip.dacq { background: #2e9e5b; }
  .dchip.dpass { background: #c2453f; }
  .dchip.derr { background: #b5b5b5; }
  .dpop { position: absolute; z-index: 30; max-width: 440px; background: #fff;
          border: 1px solid #ddd; border-radius: 10px; padding: 12px 14px;
          box-shadow: 0 8px 28px rgba(0,0,0,.14); font-size: 13px; }
  .dpop-head { font-weight: 600; margin-bottom: 6px; }
  .dpop-text { color: #444; line-height: 1.5; }
  .dpop-link { margin-top: 10px; border: 1px solid #d5d5d5; border-radius: 999px;
               background: #fff; padding: 2px 10px; font: inherit; font-size: 12px;
               cursor: pointer; color: #333; }
  .dpop-link:hover { background: #f0f2f5; }
  details.rev.flash { background: #fff8dc; transition: background 1.2s; }
  .revlist { font-size: 13px; padding: 6px 10px; }
  .revlist h2 { font-size: 15px; margin: 2px 0 8px; }
  .filterbar { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center;
               margin: 0 0 10px; }
  .fgroup { display: inline-flex; gap: 4px; align-items: center; flex-wrap: wrap; }
  .flabel { color: #888; font-size: 11px; text-transform: uppercase;
            letter-spacing: .04em; margin-right: 2px; }
  .fbtn { border: 1px solid #d5d5d5; border-radius: 999px; background: #fff;
          padding: 2px 10px; font: inherit; font-size: 12px; cursor: pointer;
          color: #333; }
  .fbtn:hover { background: #f0f2f5; }
  .fbtn.active { background: #2e9e5b; border-color: #2e9e5b; color: #fff; }
  .fcount { color: #888; font-size: 12px; margin-left: auto; }
  details.rev[hidden] { display: none; }
  details.rev { border-top: 1px solid #eee; padding: 7px 4px; }
  details.rev summary { display: flex; flex-wrap: wrap; gap: 8px;
            align-items: baseline; cursor: pointer; list-style: none; }
  details.rev summary::-webkit-details-marker { display: none; }
  details.rev summary::before { content: "\\25B8"; color: #999; font-size: 11px; }
  details.rev[open] summary::before { content: "\\25BE"; }
  .chip { border-radius: 999px; padding: 1px 9px; font-size: 11px;
          font-weight: 600; color: #fff; white-space: nowrap; }
  .chip.cond { background: #64748b; }
  .chip.acq { background: #2e9e5b; }
  .chip.passchip { background: #c2453f; }
  .chip.errchip { background: #9a9a9a; }
  .rmodel { font-weight: 600; }
  .rrun { color: #888; }
  .rscore { font-weight: 700; font-variant-numeric: tabular-nums; }
  .rtext { flex-basis: 100%; color: #444; line-height: 1.45; margin-top: 2px; }
  details.rev.err summary { opacity: 0.65; }
  .revbody { margin: 8px 0 4px 20px; color: #333; line-height: 1.5;
             border-left: 2px solid #eee; padding-left: 12px; }
  .revbody p { margin: 4px 0; }
  .revbody table { border-collapse: collapse; margin-top: 6px; }
  .revbody td { padding: 2px 10px 2px 0; vertical-align: top; }
  .revbody td.dscore { font-weight: 700; font-variant-numeric: tabular-nums; }
  .revbody pre { white-space: pre-wrap; font-size: 12px; }
  @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
"""


def to_div(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       default_height="430px", config={"responsive": True})


def thumb_data_uri(path: str, max_edge: int = 160) -> str:
    """Small base64 JPEG data URI for an artwork thumbnail, embedded inline so
    the page stays self-contained. Returns '' if the image can't be read."""
    if not path:
        return ""
    try:
        from PIL import Image
    except ImportError:
        return ""
    try:
        img = Image.open(path)
        img.load()
    except Exception:
        return ""
    img.thumbnail((max_edge, max_edge))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


FIELD_LABELS = {
    "description": "Description",
    "artist": "Artist",
    "price": "Price (USD)",
    "max_spend": "Maximum spend (USD)",
    "work_type": "Work type",
    "media_note": "Media note",
}
# Send-field name -> workbook-header key, for suppressing duplicate meta lines.
FIELD_WB_KEY = {"artist": "artist", "work_type": "work_type", "media_note": "media_note",
                "price": "artwork_price", "max_spend": "max_spend"}


def conditions_summary_html(data: dict) -> str:
    """A compact key explaining what each condition entails and which input
    values it sent — fully data-driven from the results JSON, so workbooks
    with non-A–E condition structures (e.g. pricing experiments) render too."""
    conds = data.get("conditions", {})
    items = [
        f"<li><b>{html.escape(c)}</b> — {html.escape(b.get('label', c))}</li>"
        for c, b in conds.items()
    ]
    if not items:
        return ""

    # Which conditions sent which input, and with what value. New files record
    # inputs_used per condition; old files only description_used/artist_used.
    field_value, field_conds = {}, {}
    pref_conds, prefs = [], {}
    for c, b in conds.items():
        used = b.get("inputs_used")
        if used is None:  # pre-inputs_used results format
            used = {}
            if b.get("description_used"):
                used["description"] = b["description_used"]
            if b.get("artist_used"):
                used["artist"] = b["artist_used"]
        for f, val in used.items():
            field_value.setdefault(f, val)
            field_conds.setdefault(f, []).append(c)
        if b.get("preference_variants"):
            pref_conds.append(c)
            prefs = b["preference_variants"]

    # Workbook-level metadata — skip fields already listed as condition inputs.
    wb = data.get("workbook", {})
    meta = []
    for f in ("artist", "work_type", "price", "max_spend"):
        if f not in field_value and wb.get(FIELD_WB_KEY[f]):
            meta.append(f'<div class="ctx"><b>{FIELD_LABELS[f]}:</b> '
                        f'{html.escape(str(wb[FIELD_WB_KEY[f]]))}</div>')
    if wb.get("review_prompt") is not None:
        meta.append(f'<div class="ctx"><b>System prompt:</b> review_prompt_{html.escape(str(wb["review_prompt"]))}</div>')

    ctx = []
    all_cond_keys = list(conds)
    for f, val in field_value.items():
        used_in = field_conds[f]
        where = ("all conditions" if len(used_in) == len(all_cond_keys)
                 else ", ".join(used_in))
        label = FIELD_LABELS.get(f, f.replace("_", " ").title())
        ctx.append(f'<div class="ctx"><b>{html.escape(label)}</b> '
                   f'({html.escape(where)}): {html.escape(str(val))}</div>')
    for name, text in prefs.items():
        where = ", ".join(pref_conds)
        ctx.append(f'<div class="ctx"><b>Preference - {html.escape(name)}</b> '
                   f'({html.escape(where)}): {html.escape(str(text))}</div>')
    return ('<div class="condkey"><h2>What each condition entails</h2>'
            f'<ul>{"".join(items)}</ul>{"".join(meta)}{"".join(ctx)}</div>')


def decision_table_html(df: pd.DataFrame, models: list) -> str:
    """Decision Summary card: rows = condition·preference, columns = models;
    each cell holds one chip per run — green ACQUIRE / red PASS with the
    overall score inside. Clicking a chip opens a popover with the verdict
    rationale (wired up in PICKER_JS via the data- attributes). Errors render
    as a gray × chip."""
    if df.empty:
        return ""
    vv = with_cond_pref(df)
    row_order = cond_pref_order(df)
    model_vals = [m for m in models if m in set(vv["model"])]

    head = "".join(f"<th>{html.escape(m)}</th>" for m in model_vals)
    body_rows = []
    for cp in row_order:
        cells = []
        for m in model_vals:
            sub = vv[(vv["cond_pref"] == cp) & (vv["model"] == m)].sort_values("run")
            chips = []
            for _, r in sub.iterrows():
                run_attr = str(int(r["run"])) if pd.notna(r["run"]) else ""
                if r["is_error"]:
                    review = r["review_obj"] if isinstance(r["review_obj"], dict) else {}
                    msg = (review.get("First Impression") or "").strip() or "no structured review"
                    decision, score, cls, label = "ERROR", "", "derr", "×"
                    rational = msg
                else:
                    decision = r["decision"]
                    score = f"{int(r['overall'])}" if pd.notna(r["overall"]) else "?"
                    cls = "dacq" if decision == "ACQUIRE" else "dpass"
                    label = score
                    rational = str(r["rational"])
                chips.append(
                    f'<button class="dchip {cls}"'
                    f' data-cond="{html.escape(cp)}"'
                    f' data-model="{html.escape(str(r["model"]))}"'
                    f' data-run="{run_attr}"'
                    f' data-decision="{html.escape(decision)}"'
                    f' data-score="{html.escape(score)}"'
                    f' data-rational="{html.escape(rational)}">{label}</button>')
            cells.append(f'<td>{"".join(chips)}</td>')
        body_rows.append(f'<tr><th>{html.escape(cp)}</th>{"".join(cells)}</tr>')

    return ('<div class="decsum"><h2>Decision Summary '
            '<span class="dnote">green = ACQUIRE, red = PASS · one chip per run, '
            'score inside · click a chip for the verdict rationale</span></h2>'
            f'<table><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table></div>')


def rationale_browser_html(df: pd.DataFrame, models: list) -> str:
    """The 'Verdicts & Rationales' card: one expandable row per review.
    The summary line shows condition·preference, model, run, score, decision,
    and the verdict rationale; expanding reveals the full critique (First
    Impression, Interpretation, per-dimension reasoning). Error/refusal rows
    render muted with their message."""
    if df.empty:
        return ""
    model_index = {m: i for i, m in enumerate(models)}
    cond_index = {c: i for i, c in enumerate(cond_order_of(df))}
    rows = df.sort_values(
        by=["condition", "preference_variant", "model", "run"],
        key=lambda col: (
            col.astype(str).map(cond_index).fillna(99) if col.name == "condition"
            else col.map(model_index).fillna(99) if col.name == "model"
            else col
        ),
    )

    # Filter bar values, in display order.
    conds, seen = [], set()
    for _, r in rows.iterrows():
        pv = r["preference_variant"]
        c = r["condition"] if pv == "none" else f'{r["condition"]} · {pv}'
        if c not in seen:
            seen.add(c)
            conds.append(c)
    model_vals = [m for m in models if m in set(rows["model"])]

    def fgroup(name: str, values: list) -> str:
        btns = '<button class="fbtn active" data-val="">All</button>' + "".join(
            f'<button class="fbtn" data-val="{html.escape(str(v))}">{html.escape(str(v))}</button>'
            for v in values)
        return (f'<span class="fgroup" data-group="{name}">'
                f'<span class="flabel">{name}</span>{btns}</span>')

    out = ['<div class="revlist"><h2>Verdicts &amp; Rationales</h2>'
           '<div class="filterbar">'
           + fgroup("condition", conds)
           + fgroup("model", model_vals)
           + '<span class="fcount"></span></div>']
    for _, r in rows.iterrows():
        review = r["review_obj"] if isinstance(r["review_obj"], dict) else {}
        pv = r["preference_variant"]
        cond = r["condition"] if pv == "none" else f'{r["condition"]} · {pv}'
        run = f"run {int(r['run'])}" if pd.notna(r["run"]) else "run ?"
        run_attr = str(int(r["run"])) if pd.notna(r["run"]) else ""
        attrs = (f' data-cond="{html.escape(cond)}"'
                 f' data-model="{html.escape(str(r["model"]))}"'
                 f' data-run="{run_attr}"')
        if r["is_error"]:
            msg = (review.get("First Impression") or "").strip() or "no structured review returned"
            out.append(
                f'<details class="rev err"{attrs}><summary>'
                f'<span class="chip cond">{html.escape(cond)}</span>'
                f'<span class="rmodel">{html.escape(str(r["model"]))}</span>'
                f'<span class="rrun">{run}</span>'
                f'<span class="chip errchip">ERROR</span>'
                f'<span class="rtext">{html.escape(msg)}</span></summary>'
                f'<div class="revbody"><pre>{html.escape(json.dumps(review, indent=2, ensure_ascii=False))}</pre></div>'
                f'</details>')
            continue

        decision = r["decision"]
        chip_cls = "acq" if decision == "ACQUIRE" else "passchip"
        score = f"{int(r['overall'])}" if pd.notna(r["overall"]) else "?"
        ev = review.get("Evaluation")
        ev = ev if isinstance(ev, dict) else {}
        dim_rows = "".join(
            f"<tr><td>{html.escape(dim)}</td>"
            f"<td class='dscore'>{html.escape(str((ev.get(dim) or {}).get('Score', '—')))}</td>"
            f"<td>{html.escape(str((ev.get(dim) or {}).get('Reasoning', '')))}</td></tr>"
            for dim in DIMS
        )
        body = (
            f"<p><b>First Impression.</b> {html.escape(str(review.get('First Impression', '')))}</p>"
            f"<p><b>Interpretation.</b> {html.escape(str(review.get('Interpretation', '')))}</p>"
            f"<table>{dim_rows}</table>"
        )
        out.append(
            f'<details class="rev"{attrs}><summary>'
            f'<span class="chip cond">{html.escape(cond)}</span>'
            f'<span class="rmodel">{html.escape(str(r["model"]))}</span>'
            f'<span class="rrun">{run}</span>'
            f'<span class="rscore">{score}</span>'
            f'<span class="chip {chip_cls}">{html.escape(decision)}</span>'
            f'<span class="rtext">{html.escape(str(r["rational"]))}</span></summary>'
            f'<div class="revbody">{body}</div></details>')
    out.append("</div>")
    return "".join(out)


def render_workbook(data: dict, df: pd.DataFrame) -> dict:
    """Render one workbook's section body (title, meta, conditions key, charts).
    Returns {id, title, body} for assembly into the combined page."""
    wb = data.get("workbook", {})
    models = wb.get("models") or (sorted(df["model"].dropna().unique()) if not df.empty else [])
    cmap = {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(models)}
    valid = df[~df["is_error"]] if not df.empty else df

    # Cards in display order. The model-summary heatmap and the Decision
    # Summary table are half-width so they share one grid row; the charts
    # below span the full width. None/empty entries are dropped.
    heatmap = fig_summary_heatmap(valid, models)
    decision_table = decision_table_html(df, models)
    cards = [
        (to_div(heatmap) if heatmap is not None else "", False),
        (decision_table, False),
    ] + [
        (to_div(fig), True)
        for fig in (
            fig_overall_by_condition(valid, models, cmap),
            fig_dimensions(valid, models, cmap),
            fig_decision_split(valid, models),
            fig_run_drift(valid, models, cmap),
            fig_preference(valid, models, cmap),
        ) if fig is not None
    ]
    body_cards = "".join(
        f'<div class="card{" wide" if wide else ""}">{c}</div>'
        for c, wide in cards if c
    ) or '<div class="card wide"><p>No reviews to plot yet.</p></div>'

    # The verdict-rationale browser sits right below the charts.
    rationales = rationale_browser_html(df, models)
    if rationales:
        body_cards += f'<div class="card wide">{rationales}</div>'

    # Header card: the artwork itself next to the conditions key, so the page
    # shows what is actually being judged.
    cond_summary = conditions_summary_html(data)
    art_full = thumb_data_uri(wb.get("artwork_path", ""), max_edge=520)
    art_img = f'<img class="wbart" src="{art_full}" alt="artwork">' if art_full else ""
    if cond_summary or art_img:
        body_cards = (f'<div class="card wide"><div class="wbhead">{art_img}'
                      f'{cond_summary}</div></div>') + body_cards

    title = wb.get("artwork_title") or wb.get("artwork_id") or "Workbook"
    wid = wb.get("artwork_id") or title
    n_err = int(df["is_error"].sum()) if not df.empty else 0
    meta = (f'{wb.get("artwork_id", "")} &middot; models: {", ".join(models)} '
            f'&middot; {len(df)} reviews')
    if n_err:
        meta += f' &middot; <span class="errnote">{n_err} error/refusal (excluded from charts)</span>'
    body = (f'<h2 class="wbtitle">{html.escape(title)}</h2>'
            f'<div class="meta">{meta}</div>'
            f'<div class="grid">{body_cards}</div>')
    return {"id": wid, "title": title, "body": body,
            "thumb": thumb_data_uri(wb.get("artwork_path", ""))}


PICKER_JS = """
<script>
(function () {
  function show(id) {
    document.querySelectorAll('section.wb').forEach(function (s) {
      s.hidden = (s.id !== 'wb-' + id);
    });
    document.querySelectorAll('.pick').forEach(function (b) {
      b.classList.toggle('active', b.dataset.id === id);
    });
    // Plotly charts in a previously-hidden section render at zero width;
    // resize them once the section is shown.
    document.querySelectorAll('#wb-' + id + ' .plotly-graph-div').forEach(function (gd) {
      if (window.Plotly) Plotly.Plots.resize(gd);
    });
  }
  document.querySelectorAll('.pick').forEach(function (b) {
    b.addEventListener('click', function () { show(b.dataset.id); });
  });

  // Verdicts & Rationales filters: one single-select pill group per facet
  // (condition, model, run); a row must match every group's selection.
  document.querySelectorAll('.revlist').forEach(function (list) {
    var rows = list.querySelectorAll('details.rev');
    var count = list.querySelector('.fcount');
    function apply() {
      var want = {};
      list.querySelectorAll('.fgroup').forEach(function (g) {
        want[g.dataset.group] = g.querySelector('.fbtn.active').dataset.val;
      });
      var shown = 0;
      rows.forEach(function (r) {
        var ok = (!want.condition || r.dataset.cond === want.condition)
              && (!want.model || r.dataset.model === want.model);
        r.hidden = !ok;
        if (ok) shown++;
      });
      if (count) count.textContent = shown + ' of ' + rows.length + ' reviews';
    }
    list.querySelectorAll('.fgroup').forEach(function (g) {
      g.querySelectorAll('.fbtn').forEach(function (b) {
        b.addEventListener('click', function () {
          g.querySelectorAll('.fbtn').forEach(function (x) {
            x.classList.toggle('active', x === b);
          });
          apply();
        });
      });
    });
    apply();
  });

  // Decision Summary chips: click opens a popover with the verdict rationale
  // and a jump link to the full review in the Verdicts & Rationales browser.
  var pop = document.createElement('div');
  pop.className = 'dpop';
  pop.hidden = true;
  pop.innerHTML = '<div class="dpop-head"></div><div class="dpop-text"></div>' +
                  '<button class="dpop-link">Show full review ↓</button>';
  document.body.appendChild(pop);
  var popChip = null;

  pop.querySelector('.dpop-link').addEventListener('click', function () {
    if (!popChip) return;
    var d = popChip.dataset;
    var sec = popChip.closest('section.wb');
    // Reset the browser's filters so the target row can't be hidden.
    sec.querySelectorAll('.fgroup').forEach(function (g) {
      var all = g.querySelector('.fbtn[data-val=""]');
      if (all && !all.classList.contains('active')) all.click();
    });
    sec.querySelectorAll('details.rev').forEach(function (r) {
      if (r.dataset.cond === d.cond && r.dataset.model === d.model
          && r.dataset.run === d.run) {
        r.open = true;
        r.scrollIntoView({ behavior: 'smooth', block: 'center' });
        r.classList.add('flash');
        setTimeout(function () { r.classList.remove('flash'); }, 1600);
      }
    });
    pop.hidden = true;
  });

  document.addEventListener('click', function (e) {
    var chip = e.target.closest('.dchip');
    if (!chip) {
      if (!e.target.closest('.dpop')) pop.hidden = true;
      return;
    }
    if (chip === popChip && !pop.hidden) { pop.hidden = true; popChip = null; return; }
    popChip = chip;
    var d = chip.dataset;
    pop.querySelector('.dpop-head').textContent =
      d.cond + ' · ' + d.model + ' · run ' + d.run + ' — ' + d.decision
      + (d.score ? ' ' + d.score : '');
    pop.querySelector('.dpop-text').textContent = d.rational || '';
    pop.hidden = false;
    var r = chip.getBoundingClientRect();
    var left = Math.min(r.left + window.scrollX,
                        window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 16);
    pop.style.left = Math.max(left, window.scrollX + 8) + 'px';
    pop.style.top = (r.bottom + window.scrollY + 8) + 'px';
  });
})();
</script>
"""


def build_combined_html(workbooks: list, default_id: str, offline: bool) -> str:
    """One page holding every workbook section, with a thumbnail strip to switch."""
    plotly_js = (f"<script>{plotly.offline.get_plotlyjs()}</script>" if offline
                 else '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')
    picks = "".join(
        f'<button class="pick{" active" if w["id"] == default_id else ""}" '
        f'data-id="{html.escape(w["id"])}" title="{html.escape(w["title"])}">'
        + (f'<img src="{w["thumb"]}" alt="">' if w.get("thumb") else '<div class="noimg"></div>')
        + f'<span class="pid">{html.escape(w["id"])}</span>'
        f'<span class="pttl">{html.escape(w["title"])}</span></button>'
        for w in workbooks)
    sections = "".join(
        f'<section class="wb" id="wb-{html.escape(w["id"])}"'
        f'{"" if w["id"] == default_id else " hidden"}>{w["body"]}</section>'
        for w in workbooks)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Workbook Dashboards</title>{plotly_js}<style>{CSS}</style>"
        "</head><body>"
        '<div class="topbar"><h1>Workbook Dashboards</h1>'
        f'<div class="picker-bar">{picks}</div></div>'
        f"{sections}{PICKER_JS}</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build one combined dashboard covering every workbook in results/.")
    parser.add_argument("results", nargs="?", type=Path, default=None,
                        help="(optional, ignored) the combined dashboard always covers "
                             "every results/*.json — pass a path only out of habit")
    parser.add_argument("--out", type=Path, default=None,
                        help="output HTML path (default: dashboards/index.html)")
    parser.add_argument("--offline", action="store_true",
                        help="inline Plotly.js so the page works with no internet (~3.5 MB)")
    parser.add_argument("--open", dest="open_browser", action="store_true",
                        help="open the dashboard in a browser when done")
    args = parser.parse_args()

    results_dir = REPO_ROOT / "results"
    files = sorted(p for p in results_dir.glob("*.json") if not p.name.endswith(".summary.json"))
    if not files:
        sys.exit("error: no results/*.json found.")

    entries = []  # (mtime, workbook-dict) — sorted by id for the picker
    for f in files:
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            print(f"skipping {f.name}: invalid JSON ({exc})", file=sys.stderr)
            continue
        entries.append((f.stat().st_mtime, render_workbook(data, flatten(data))))
    if not entries:
        sys.exit("error: no readable results files.")

    workbooks = [w for _, w in entries]
    default_id = max(entries, key=lambda e: e[0])[1]["id"]  # newest run shown first

    out_path = args.out or (REPO_ROOT / "dashboards" / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_combined_html(workbooks, default_id, args.offline))

    print(f"Wrote {out_path}  ({len(workbooks)} workbooks; showing {default_id} by default)")
    if args.open_browser:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
