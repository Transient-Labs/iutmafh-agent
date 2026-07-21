#!/usr/bin/env python3
"""Cross-experiment comparison dashboard.

Scans results/experiment-*/ (each a finished sweep with TEST-*.json files and
its own baked per-experiment dashboard), and builds ONE self-contained HTML
page at dashboards/compare.html that puts the experiments side by side:

- a summary table (models, prompt version, mean overall, ACQUIRE rate) with
  links to each experiment's full dashboard
- mean overall score by condition x experiment, artwork x experiment heatmap,
  model-family split, and ACQUIRE-rate comparison
- a decision-flip section: which (artwork, condition, model family) verdicts
  changed between experiments, as a flip map + verdict table
- a side-by-side viewer that loads any two of the existing per-experiment
  dashboards in iframes

Experiment labels are derived from each run's own workbook metadata (models +
review_prompt) — nothing to maintain by hand. results/archive-*/ is never
scanned. dashboard.py is reused as a library and is not modified.

Usage:
    uv run python art_reviewer_sdk/compare_dashboards.py            # dashboards/compare.html
    uv run python art_reviewer_sdk/compare_dashboards.py --open     # ...and open it
    uv run python art_reviewer_sdk/compare_dashboards.py --offline  # inline Plotly.js
"""

import argparse
import html
import json
import sys
import webbrowser
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.offline

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from dashboard import (  # noqa: E402  (path set above)
    CSS as BASE_CSS,
    DECISION_COLORS,
    cond_pref_order,
    flatten,
    thumb_data_uri,
    to_div,
    with_cond_pref,
)

VERDICT_COLORS = {**DECISION_COLORS, "SPLIT": "#d99a2b", "—": "#b5b5b5"}


def _exp_sort_key(p: Path):
    """experiment-2 before experiment-10."""
    tail = p.name.rsplit("-", 1)[-1]
    return (0, int(tail)) if tail.isdigit() else (1, p.name)


def discover_experiments(results_dir: Path) -> list[dict]:
    """One entry per results/experiment-*/ directory, labelled from the
    workbook metadata of its first results file."""
    experiments = []
    for d in sorted(results_dir.glob("experiment-*"), key=_exp_sort_key):
        if not d.is_dir():
            continue
        files = sorted(p for p in d.glob("TEST-*.json")
                       if not p.name.endswith(".summary.json"))
        if not files:
            print(f"skipping {d.name}: no TEST-*.json files", file=sys.stderr)
            continue
        try:
            wb = json.loads(files[0].read_text()).get("workbook", {})
        except json.JSONDecodeError as exc:
            print(f"skipping {d.name}: unreadable {files[0].name} ({exc})",
                  file=sys.stderr)
            continue
        models = wb.get("models", [])
        prompt = wb.get("review_prompt", "?")
        experiments.append({
            "name": d.name,
            "dir": d,
            "files": files,
            "models": models,
            "prompt": prompt,
            "label": f"{d.name} — {' + '.join(models)} · v{prompt}",
            "dashboard": d / "index.html",  # baked per-experiment dashboard
        })
    return experiments


def model_family(model: str) -> str:
    """Vendor family key so per-model comparisons line up across experiments
    that used different concrete model IDs (gpt-5-mini vs gpt-5, ...)."""
    return str(model or "").split("-")[0] or "?"


def load_all(experiments: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Concat every experiment's reviews into one frame (one row per review,
    via dashboard.flatten) plus per-artwork metadata for the flip table."""
    frames, artworks = [], {}
    cond_order: list = []
    for exp in experiments:
        for f in exp["files"]:
            try:
                data = json.loads(f.read_text())
            except json.JSONDecodeError as exc:
                print(f"skipping {f}: invalid JSON ({exc})", file=sys.stderr)
                continue
            df = flatten(data)
            if df.empty:
                continue
            wb = data.get("workbook", {})
            aid = wb.get("artwork_id") or f.stem
            df["experiment"] = exp["name"]
            df["exp_label"] = exp["label"]
            df["artwork_id"] = aid
            df["artwork_title"] = wb.get("artwork_title", "")
            df["model_family"] = df["model"].map(model_family)
            # Every chart series is one experiment × one concrete model —
            # GPT and Gemini results are never pooled into one number.
            df["series"] = exp["name"] + " · " + df["model"].astype(str)
            for c in df["condition"].cat.categories:
                if c not in cond_order:
                    cond_order.append(c)
            frames.append(df)
            if aid not in artworks:
                artworks[aid] = {
                    "title": wb.get("artwork_title", ""),
                    "thumb": thumb_data_uri(wb.get("artwork_path", "")),
                }
    if not frames:
        sys.exit("error: no readable results in the experiment directories.")
    df = pd.concat(frames, ignore_index=True)
    # concat degrades the per-file ordered categorical; restore a global order.
    df["condition"] = pd.Categorical(df["condition"].astype(str),
                                     categories=cond_order, ordered=True)
    return with_cond_pref(df), artworks


def unit_verdict(decisions: pd.Series) -> str:
    """Majority ACQUIRE/PASS over a group of (non-error) runs; an exact tie
    is SPLIT; no valid runs is —. Used by the artwork verdict map."""
    d = decisions[decisions.isin(["ACQUIRE", "PASS"])]
    if d.empty:
        return "—"
    acq, n = int((d == "ACQUIRE").sum()), len(d)
    return "ACQUIRE" if acq * 2 > n else "PASS" if acq * 2 < n else "SPLIT"


# ---- overall-score / decision figures ----
# One series per experiment × model (never pooled across models).

def series_order(experiments: list[dict]) -> list[str]:
    return [f"{e['name']} · {m}" for e in experiments for m in e["models"]]


# One hue per experiment; models within it are shades of that hue.
EXP_BASE_COLORS = ["#2e9e5b", "#3b76d1", "#d97b2e", "#8b5cd6",
                   "#c2453f", "#3aa6a6"]


def _shade(hex_color: str, factor: float) -> str:
    """Blend toward white (factor > 0) or black (factor < 0)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    target = 255 if factor > 0 else 0
    f = abs(factor)
    return "#{:02x}{:02x}{:02x}".format(
        *(round(c + (target - c) * f) for c in (r, g, b)))


def _series_cmap(experiments: list[dict]) -> dict:
    """experiment hue × model shade: gpt models darker, gemini lighter, any
    other family spread across shades by position."""
    cmap = {}
    for i, e in enumerate(experiments):
        base = EXP_BASE_COLORS[i % len(EXP_BASE_COLORS)]
        n = len(e["models"])
        for j, m in enumerate(e["models"]):
            fam = model_family(m)
            if fam == "gpt":
                f = -0.35
            elif fam == "gemini":
                f = 0.4
            else:
                f = (j / max(n - 1, 1) - 0.5) * 0.7
            cmap[f"{e['name']} · {m}"] = _shade(base, f)
    return cmap


def fig_exp_condition_bars(df: pd.DataFrame, experiments: list[dict], order: list):
    valid = df[~df["is_error"] & df["overall"].notna()]
    agg = (valid.groupby(["cond_pref", "series"], observed=True)["overall"]
                .agg(["mean", "std"]).reset_index())
    fig = px.bar(agg, x="cond_pref", y="mean", color="series", error_y="std",
                 barmode="group", color_discrete_map=_series_cmap(experiments),
                 category_orders={"cond_pref": order,
                                  "series": series_order(experiments)},
                 labels={"cond_pref": "condition", "mean": "mean overall score",
                         "series": ""},
                 title="Mean overall score — condition × experiment · model")
    fig.update_yaxes(range=[0, 100])
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.3))
    return fig


def fig_exp_artwork_heatmap(df: pd.DataFrame, experiments: list[dict],
                            artworks: dict):
    valid = df[~df["is_error"] & df["overall"].notna()]
    cols = series_order(experiments)
    mean = (valid.groupby(["artwork_id", "series"], observed=True)["overall"]
                 .mean().unstack("series").reindex(columns=cols))
    titles = [f"{aid} — {artworks.get(aid, {}).get('title', '')}"
              for aid in mean.index]
    fig = go.Figure(go.Heatmap(
        z=mean.values, x=cols, y=list(mean.index),
        customdata=[[t] * len(cols) for t in titles],
        colorscale="RdYlGn", zmin=0, zmax=100, xgap=2, ygap=2,
        texttemplate="%{z:.0f}", textfont={"size": 10},
        hovertemplate="%{customdata[0]}<br>%{x}: mean overall %{z:.1f}<extra></extra>",
        colorbar={"title": "mean"},
    ))
    fig.update_layout(title="Mean overall score — artwork × experiment · model",
                      margin=dict(l=10, r=10, t=50, b=10),
                      yaxis={"autorange": "reversed", "dtick": 1},
                      xaxis={"tickfont": {"size": 10}})
    return fig


def fig_exp_acquire_rate(df: pd.DataFrame, experiments: list[dict], order: list):
    valid = df[~df["is_error"]]
    rate = (valid.groupby(["cond_pref", "series"], observed=True)["decision"]
                 .apply(lambda d: 100.0 * (d == "ACQUIRE").mean()).reset_index())
    fig = px.bar(rate, x="cond_pref", y="decision", color="series",
                 barmode="group", color_discrete_map=_series_cmap(experiments),
                 category_orders={"cond_pref": order,
                                  "series": series_order(experiments)},
                 labels={"cond_pref": "condition", "decision": "ACQUIRE rate (%)",
                         "series": ""},
                 title="ACQUIRE rate — condition × experiment · model")
    fig.update_yaxes(range=[0, 100])
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.3))
    return fig


# ---- artwork zoom (per-artwork condition comparison) ----

VERDICT_Z = {"PASS": 0, "SPLIT": 1, "ACQUIRE": 2}


def fig_art_condition_bars(sub: pd.DataFrame, experiments: list[dict],
                           order: list, aid: str):
    valid = sub[~sub["is_error"] & sub["overall"].notna()]
    if valid.empty:
        return None
    agg = (valid.groupby(["cond_pref", "series"], observed=True)["overall"]
                .agg(["mean", "std"]).reset_index())
    fig = px.bar(agg, x="cond_pref", y="mean", color="series", error_y="std",
                 barmode="group", color_discrete_map=_series_cmap(experiments),
                 category_orders={"cond_pref": order,
                                  "series": series_order(experiments)},
                 labels={"cond_pref": "condition", "mean": "mean overall score",
                         "series": ""},
                 title=f"{aid} — mean overall score by condition (mean of runs)")
    fig.update_yaxes(range=[0, 100])
    fig.update_layout(margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.3))
    return fig


def fig_art_verdict_map(sub: pd.DataFrame, experiments: list[dict],
                        order: list, aid: str):
    """Majority ACQUIRE/PASS verdict per experiment·model × condition for one
    artwork, with the mean overall score printed in each cell."""
    valid = sub[~sub["is_error"]]
    if valid.empty:
        return None
    rows = series_order(experiments)[::-1]  # first series on top
    verdict = (valid.groupby(["series", "cond_pref"], observed=True)["decision"]
                    .apply(unit_verdict).unstack("cond_pref")
                    .reindex(index=rows, columns=order))
    mean = (valid.groupby(["series", "cond_pref"], observed=True)["overall"]
                 .mean().unstack("cond_pref").reindex(index=rows, columns=order))
    z = verdict.map(lambda v: VERDICT_Z.get(v)).astype(float)
    text = mean.round(0).map(lambda v: "" if pd.isna(v) else f"{v:.0f}")
    fig = go.Figure(go.Heatmap(
        z=z.values, x=order, y=rows,
        text=text.values, texttemplate="%{text}", textfont={"size": 11},
        customdata=verdict.values,
        colorscale=[[0, DECISION_COLORS["PASS"]], [0.5, VERDICT_COLORS["SPLIT"]],
                    [1, DECISION_COLORS["ACQUIRE"]]],
        zmin=0, zmax=2, xgap=3, ygap=3, showscale=False,
        hovertemplate="%{y}<br>%{x}: %{customdata} · mean overall %{text}"
                      "<extra></extra>",
    ))
    fig.update_layout(
        title=f"{aid} — majority verdict per condition "
              "(green ACQUIRE · amber SPLIT · red PASS; number = mean overall)",
        margin=dict(l=10, r=10, t=50, b=10),
        yaxis={"dtick": 1, "tickfont": {"size": 10}})
    return fig


OVERVIEW_ID = "__overview"

PICKER_JS = """
<script>
  (function () {
    const picker = document.querySelector('.azpicker');
    picker.addEventListener('click', function (ev) {
      const btn = ev.target.closest('.pick');
      if (!btn) return;
      picker.querySelectorAll('.pick').forEach(
        b => b.classList.toggle('active', b === btn));
      document.querySelectorAll('section.az').forEach(s => {
        s.hidden = (s.id !== 'az-' + btn.dataset.id);
        if (!s.hidden) s.querySelectorAll('.plotly-graph-div').forEach(
          gd => window.Plotly && Plotly.Plots.resize(gd));
      });
    });
  })();
</script>"""


def picker_html(df: pd.DataFrame, artworks: dict) -> str:
    """Sticky top strip: Overview (default) + one thumbnail per artwork."""
    picks = [
        f'<button class="pick active" data-id="{OVERVIEW_ID}" '
        'title="All artworks combined"><div class="noimg ovicon">ALL</div>'
        '<span class="pid">Overview</span>'
        '<span class="pttl">all artworks</span></button>']
    for aid in sorted(df["artwork_id"].unique()):
        art = artworks.get(aid, {})
        thumb = (f'<img src="{art["thumb"]}" alt="">' if art.get("thumb")
                 else '<div class="noimg"></div>')
        picks.append(
            f'<button class="pick" data-id="{html.escape(aid)}" '
            f'title="{html.escape(art.get("title", ""))}">{thumb}'
            f'<span class="pid">{html.escape(aid)}</span>'
            f'<span class="pttl">{html.escape(art.get("title", ""))}</span></button>')
    return f'<div class="azpicker picker-bar">{"".join(picks)}</div>'


def artwork_sections_html(df: pd.DataFrame, experiments: list[dict],
                          order: list) -> str:
    """One hidden pre-rendered section per artwork (revealed by the picker),
    so the page stays fully self-contained."""
    n_series = len(series_order(experiments))
    sections = []
    for aid in sorted(df["artwork_id"].unique()):
        sub = df[df["artwork_id"] == aid]
        bars = fig_art_condition_bars(sub, experiments, order, aid)
        vmap = fig_art_verdict_map(sub, experiments, order, aid)
        body = (
            (f'<div class="card wide">{to_div(bars)}</div>' if bars else "")
            + (f'<div class="card wide">{to_div_tall(vmap, n_series)}</div>'
               if vmap else "")
            or '<div class="card wide meta">no valid reviews</div>')
        sections.append(f'<section class="az" id="az-{html.escape(aid)}" hidden>'
                        f'<div class="grid">{body}</div></section>')
    return "".join(sections)


# ---- page sections ----

def _dash_href(exp: dict) -> str:
    """Relative link from dashboards/ to the experiment's baked dashboard."""
    return f'../results/{exp["name"]}/index.html'


def experiments_summary_html(experiments: list[dict], df: pd.DataFrame) -> str:
    """One row per experiment × model — per-model stats are never pooled."""
    rows = []
    for e in experiments:
        span = len(e["models"])
        link = (f'<a href="{_dash_href(e)}" target="_blank">open ↗</a>'
                if e["dashboard"].is_file() else '<span class="meta">—</span>')
        for i, m in enumerate(e["models"]):
            sub = df[(df["experiment"] == e["name"]) & (df["model"] == m)]
            valid = sub[~sub["is_error"]]
            mean = valid["overall"].mean()
            acq = (100.0 * (valid["decision"] == "ACQUIRE").mean()
                   if len(valid) else 0.0)
            exp_cells = (f'<td rowspan="{span}"><b>{html.escape(e["name"])}</b></td>'
                         f'<td rowspan="{span}">v{html.escape(str(e["prompt"]))}</td>'
                         if i == 0 else "")
            end_cell = f'<td rowspan="{span}">{link}</td>' if i == 0 else ""
            rows.append(
                f"<tr>{exp_cells}<td>{html.escape(m)}</td>"
                f"<td>{len(sub)}</td><td>{int(sub['is_error'].sum())}</td>"
                f"<td>{mean:.1f}</td><td>{acq:.0f}%</td>{end_cell}</tr>")
    return f"""
<div class="decsum expsum">
  <h2>Experiments</h2>
  <table>
    <thead><tr><th>Experiment</th><th>Prompt</th><th>Model</th><th>Reviews</th>
    <th>Errors</th><th>Mean overall</th><th>ACQUIRE</th><th>Dashboard</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>"""


def side_by_side_html(experiments: list[dict]) -> str:
    """Two iframe panes with experiment pickers. Iframes stay empty until an
    experiment is picked, so the multi-MB dashboards load lazily."""
    def options(selected: str) -> str:
        opts = ['<option value="">— choose experiment —</option>']
        for e in experiments:
            if not e["dashboard"].is_file():
                continue
            sel = " selected" if e["name"] == selected else ""
            opts.append(f'<option value="{_dash_href(e)}"{sel}>'
                        f'{html.escape(e["label"])}</option>')
        return "".join(opts)

    with_dash = [e for e in experiments if e["dashboard"].is_file()]
    left = with_dash[0]["name"] if with_dash else ""
    right = with_dash[-1]["name"] if len(with_dash) > 1 else ""
    panes = "".join(f"""
  <div class="pane">
    <div class="panebar">
      <select class="exp-pick">{options(sel)}</select>
      <a class="openfull" target="_blank" hidden>open full ↗</a>
    </div>
    <iframe loading="lazy"></iframe>
  </div>""" for sel in (left, right))
    return f"""
<h2 class="sbstitle">Side by side — full experiment dashboards</h2>
<div class="sbs">{panes}</div>
<script>
  document.querySelectorAll('.pane').forEach(pane => {{
    const pick = pane.querySelector('.exp-pick');
    const frame = pane.querySelector('iframe');
    const link = pane.querySelector('.openfull');
    const apply = () => {{
      if (pick.value) {{ frame.src = pick.value; link.href = pick.value; }}
      else {{ frame.removeAttribute('src'); }}
      link.toggleAttribute('hidden', !pick.value);
    }};
    pick.addEventListener('change', apply);
    apply();  // load the preselected defaults
  }});
</script>"""


COMPARE_CSS = """
  .expsum td, .expsum thead th { padding-right: 18px; }
  .sbstitle { font-size: 17px; margin: 26px 0 10px; }
  section.az[hidden] { display: none; }
  .ovicon { display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 13px; color: #666; letter-spacing: .04em; }
  .sbs { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .pane { display: flex; flex-direction: column; gap: 6px; }
  .panebar { display: flex; gap: 10px; align-items: center; }
  .exp-pick { font: inherit; font-size: 13px; padding: 4px 8px;
      border: 1px solid #d5d5d5; border-radius: 8px; background: #fff;
      max-width: 100%; }
  .openfull { font-size: 12px; color: #2e9e5b; white-space: nowrap; }
  .pane iframe { width: 100%; height: 78vh; border: 1px solid #e6e6e6;
      border-radius: 10px; background: #fff; }
  @media (max-width: 1100px) { .sbs { grid-template-columns: 1fr; } }
"""


def to_div_tall(fig, rows: int) -> str:
    """Chart div sized to its row count (artwork heatmaps outgrow 430px)."""
    h = max(430, 60 + 26 * rows)
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       default_height=f"{h}px", config={"responsive": True})


def build_page(experiments: list[dict], df: pd.DataFrame, artworks: dict,
               offline: bool) -> str:
    plotly_js = (f"<script>{plotly.offline.get_plotlyjs()}</script>" if offline
                 else '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>')
    order = cond_pref_order(df)
    n_art = df["artwork_id"].nunique()

    overview = (
        f'<section class="az" id="az-{OVERVIEW_ID}">'
        f'<div class="meta">{len(experiments)} experiments · {n_art} artworks · '
        f'{len(df)} reviews. Numeric charts exclude error/refusal reviews.</div>'
        '<div class="grid">'
        f'<div class="card wide">{experiments_summary_html(experiments, df)}</div>'
        f'<div class="card wide">{to_div(fig_exp_condition_bars(df, experiments, order))}</div>'
        f'<div class="card wide">{to_div(fig_exp_acquire_rate(df, experiments, order))}</div>'
        f'<div class="card wide">{to_div_tall(fig_exp_artwork_heatmap(df, experiments, artworks), n_art)}</div>'
        "</div></section>"
    )
    body = (
        '<div class="topbar"><h1>Experiment comparison</h1>'
        + picker_html(df, artworks) + "</div>"
        + overview
        + artwork_sections_html(df, experiments, order)
        + PICKER_JS
        + side_by_side_html(experiments)
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Experiment Comparison</title>{plotly_js}"
        f"<style>{BASE_CSS}{COMPARE_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a cross-experiment comparison dashboard from "
                    "results/experiment-*/.")
    parser.add_argument("--out", type=Path, default=None,
                        help="output HTML path (default: dashboards/compare.html)")
    parser.add_argument("--offline", action="store_true",
                        help="inline Plotly.js so the page works with no internet (~3.5 MB)")
    parser.add_argument("--open", dest="open_browser", action="store_true",
                        help="open the page in a browser when done")
    args = parser.parse_args()

    experiments = discover_experiments(REPO_ROOT / "results")
    if len(experiments) < 2:
        sys.exit("error: need at least two results/experiment-*/ directories "
                 "with TEST-*.json files to compare.")
    df, artworks = load_all(experiments)

    out_path = args.out or (REPO_ROOT / "dashboards" / "compare.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_page(experiments, df, artworks, args.offline))

    print(f"Wrote {out_path}  ({len(experiments)} experiments: "
          f"{', '.join(e['label'] for e in experiments)})")
    if args.open_browser:
        webbrowser.open(out_path.resolve().as_uri())


if __name__ == "__main__":
    main()
