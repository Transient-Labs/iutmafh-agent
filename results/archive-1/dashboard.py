#!/usr/bin/env python3
"""ARCHIVED dashboard — frozen copy for the older (pre-A–E) workbook results.

A standalone snapshot of the dashboard that scans the results JSON files in
THIS folder (results/archive/) and builds results/archive/index.html. It is
self-contained (dimension names inlined) so it keeps rendering the archived
tests regardless of future changes to the live SDK dashboard. Editing the live
art_reviewer_sdk/dashboard.py does NOT affect this one.

Usage:
    uv run python results/archive/dashboard.py            # rebuild results/archive/index.html
    uv run python results/archive/dashboard.py --open     # ...and open it
    uv run python results/archive/dashboard.py --offline  # inline Plotly.js (no internet)
"""

import argparse
import base64
import html
import io
import json
import sys
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.offline

HERE = Path(__file__).resolve().parent  # this archive folder; results live here

# Dimension names inlined so this archived dashboard stands alone (no dependency
# on the live SDK, which may change). These match the recorded results.
DIMS = ["Craft", "Composition", "Originality", "Emotional Resonance", "Conceptual Depth"]
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


def cond_pref_order(v):
    """Ordered cond_pref categories: A, B, then C/D split by variant."""
    order = []
    for c in COND_ORDER:
        for pv in sorted(v.loc[v["condition"] == c, "preference_variant"].unique()):
            order.append(c if pv == "none" else f"{c} · {pv}")
    return order


def _clean_facet_titles(fig):
    """Strip the "col=" prefix Plotly adds to facet titles."""
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    return fig


# ---- individual figures (return None when there's nothing to plot) ----

def fig_overall_by_condition(v, models, cmap):
    if v.empty:
        return None
    vv = with_cond_pref(v)
    fig = px.box(vv, x="cond_pref", y="overall", color="model", points="all",
                 category_orders={"cond_pref": cond_pref_order(v), "model": models},
                 color_discrete_map=cmap, boxmode="group",
                 hover_data=["condition", "preference_variant", "run"],
                 title="Overall Score by Condition & Preference (context effect)")
    fig.update_layout(yaxis_range=[0, 100], xaxis_title="condition · preference")
    return fig


def fig_dimensions(v, models, cmap):
    if v.empty:
        return None
    long = v.melt(id_vars=["model"], value_vars=DIMS,
                  var_name="dimension", value_name="score").dropna(subset=["score"])
    if long.empty:
        return None
    fig = px.box(long, x="dimension", y="score", color="model", points="all",
                 category_orders={"dimension": DIMS, "model": models},
                 color_discrete_map=cmap, boxmode="group",
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
                  markers=True,
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


def conditions_summary_html(data: dict) -> str:
    """A compact key explaining what each condition (and the C/D preference
    variants) entails, pulled straight from the results JSON."""
    conds = data.get("conditions", {})
    items = [
        f"<li><b>{c}</b> — {html.escape(conds[c].get('label', c))}</li>"
        for c in COND_ORDER if c in conds
    ]
    if not items:
        return ""
    # Scan all conditions for the first non-empty value (description lives in
    # B/D/E, preferences in E) — data-driven so old 4-condition files still work.
    desc = next((conds[c].get("description_used") for c in COND_ORDER
                 if c in conds and conds[c].get("description_used")), "")
    prefs = next((conds[c].get("preference_variants") for c in COND_ORDER
                  if c in conds and conds[c].get("preference_variants")), {})

    # Workbook-level metadata (artist, price, prompt version) — recorded in the
    # results JSON header by the harness.
    wb = data.get("workbook", {})
    meta = []
    if wb.get("artist"):
        meta.append(f'<div class="ctx"><b>Artist:</b> {html.escape(str(wb["artist"]))}</div>')
    if wb.get("work_type"):
        meta.append(f'<div class="ctx"><b>Work type:</b> {html.escape(str(wb["work_type"]))}</div>')
    if wb.get("artwork_price"):
        meta.append(f'<div class="ctx"><b>Price (USD):</b> {html.escape(str(wb["artwork_price"]))}</div>')
    if wb.get("max_spend"):
        meta.append(f'<div class="ctx"><b>Maximum spend (USD):</b> {html.escape(str(wb["max_spend"]))}</div>')
    if wb.get("review_prompt") is not None:
        meta.append(f'<div class="ctx"><b>System prompt:</b> review_prompt_{html.escape(str(wb["review_prompt"]))}</div>')

    ctx = []
    if desc:
        ctx.append(f'<div class="ctx"><b>Description</b> (used in B &amp; D): {html.escape(desc)}</div>')
    for name, text in prefs.items():
        ctx.append(f'<div class="ctx"><b>Preference - {html.escape(name)}</b> (C &amp; D): {html.escape(text)}</div>')
    return ('<div class="condkey"><h2>What each condition entails</h2>'
            f'<ul>{"".join(items)}</ul>{"".join(meta)}{"".join(ctx)}</div>')


def render_workbook(data: dict, df: pd.DataFrame) -> dict:
    """Render one workbook's section body (title, meta, conditions key, charts).
    Returns {id, title, body} for assembly into the combined page."""
    wb = data.get("workbook", {})
    models = wb.get("models") or (sorted(df["model"].dropna().unique()) if not df.empty else [])
    cmap = {m: PALETTE[i % len(PALETTE)] for i, m in enumerate(models)}
    valid = df[~df["is_error"]] if not df.empty else df

    # (figure, wide?) in display order; None figures are dropped.
    cards = [
        (fig_summary_heatmap(valid, models), True),
        (fig_overall_by_condition(valid, models, cmap), True),
        (fig_dimensions(valid, models, cmap), True),
        (fig_decision_split(valid, models), True),
        (fig_run_drift(valid, models, cmap), True),
        (fig_preference(valid, models, cmap), True),
    ]
    body_cards = "".join(
        f'<div class="card{" wide" if wide else ""}">{to_div(fig)}</div>'
        for fig, wide in cards if fig is not None
    ) or '<div class="card wide"><p>No reviews to plot yet.</p></div>'

    cond_summary = conditions_summary_html(data)
    if cond_summary:
        body_cards = f'<div class="card wide">{cond_summary}</div>' + body_cards

    title = wb.get("artwork_title") or wb.get("artwork_id") or "Workbook"
    wid = wb.get("artwork_id") or title
    meta = (f'{wb.get("artwork_id", "")} &middot; models: {", ".join(models)} '
            f'&middot; {len(df)} reviews')
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

    results_dir = HERE  # the archive folder this script lives in
    files = sorted(p for p in results_dir.glob("*.json") if not p.name.endswith(".summary.json"))
    if not files:
        sys.exit(f"error: no *.json results found in {results_dir}.")

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

    out_path = args.out or (HERE / "index.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_combined_html(workbooks, default_id, args.offline))

    print(f"Wrote {out_path}  ({len(workbooks)} workbooks; showing {default_id} by default)")
    if args.open_browser:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
