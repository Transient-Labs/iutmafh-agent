#!/usr/bin/env python3
"""Publication figures for the whitepaper, rendered from reviews.csv.

Every number is recomputed from whitepaper_info/reviews.csv (the source of
truth); nothing is hard-coded. Figures are written as high-DPI PNGs into
whitepaper_info/figures/ for embedding in whitepaper.html and screenshotting
into the working Google Doc.

Run:
    uv run --with matplotlib python art_reviewer_sdk/paper_figures.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parent.parent
INFO = REPO_ROOT / "whitepaper_info"
FIGDIR = INFO / "figures"

# Display names and a fixed order, grouped by family (economic then frontier).
MODEL_ORDER = ["gpt-5-mini", "gpt-5",
               "gemini-2.5-flash", "gemini-3-flash-preview",
               "claude-haiku-4-5", "claude-sonnet-4-6"]
MODEL_LABEL = {"gemini-2.5-flash": "Gemini 2.5 Flash",
               "gpt-5-mini": "GPT-5 Mini",
               "gemini-3-flash-preview": "Gemini 3 Flash Preview",
               "gpt-5": "GPT-5",
               "claude-haiku-4-5": "Claude Haiku 4.5",
               "claude-sonnet-4-6": "Claude Sonnet 4.6"}
# Prompt colors, reused across figures.
C_V4, C_V5 = "#4c6fa5", "#d98a3d"      # directive (blue), minimal (orange)
# Per-model colors (family = hue, tier = shade) for the run-level example.
MODEL_COLOR = {"gpt-5": "#1f4e79", "gpt-5-mini": "#5b93c4",
               "gemini-3-flash-preview": "#b5651d", "gemini-2.5-flash": "#e0a45e",
               "claude-sonnet-4-6": "#2e7d4f", "claude-haiku-4-5": "#74c493"}
# Genre labels for all 22 artworks (used in artwork heatmap row labels).
GENRE = {"TEST-001": "Glitch", "TEST-002": "Digital Painting",
         "TEST-003": "Digital Painting", "TEST-004": "Digital Painting",
         "TEST-005": "CryptoPunk PFP", "TEST-006": "Glitch Art PFP",
         "TEST-007": "Generative PFP", "TEST-008": "Photography",
         "TEST-009": "Photography", "TEST-010": "AI Generated",
         "TEST-011": "Digital Painting", "TEST-012": "Abstract Digital",
         "TEST-013": "Glitch", "TEST-014": "Traditional Painting",
         "TEST-015": "Traditional Painting", "TEST-016": "Photography",
         "TEST-017": "Generative Art", "TEST-018": "Photography",
         "TEST-019": "Abstract Physical", "TEST-020": "Physical Drawing",
         "TEST-021": "Photography", "TEST-022": "Glitch"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True,
    "grid.color": "#e6e6e6", "figure.dpi": 160,
})


def load_groups() -> pd.DataFrame:
    """One row per complete review group (3 valid runs), with decision
    unanimity and overall-score spread."""
    df = pd.read_csv(INFO / "reviews.csv")
    df["preference_variant"] = df["preference_variant"].fillna("none")
    keys = ["review_prompt", "artwork_id", "condition", "preference_variant", "model"]

    def valid(s):
        return s[df.loc[s.index, "is_error"] == False]  # noqa: E712

    g = df.groupby(keys, observed=True)
    grp = g.agg(nruns=("run", "size"), nerr=("is_error", "sum"),
                ndec=("decision", lambda s: valid(s).nunique()),
                srange=("overall", lambda s: valid(s).max() - valid(s).min()),
                ssd=("overall", lambda s: valid(s).std(ddof=0))).reset_index()
    grp = grp[(grp["nruns"] == 3) & (grp["nerr"] == 0)].copy()
    grp["unanimous"] = grp["ndec"] == 1
    return grp


def grouped_bars(ax, rate_v4, rate_v5, ylabel, fmt="{:.0f}"):
    x = np.arange(len(MODEL_ORDER))
    w = 0.38
    b1 = ax.bar(x - w / 2, rate_v4, w, label="v4 directive", color=C_V4)
    b2 = ax.bar(x + w / 2, rate_v5, w, label="v5 minimal", color=C_V5)
    for bars in (b1, b2):
        for r in bars:
            ax.annotate(fmt.format(r.get_height()),
                        (r.get_x() + r.get_width() / 2, r.get_height()),
                        ha="center", va="bottom", fontsize=10,
                        xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_LABEL[m] for m in MODEL_ORDER], fontsize=9,
                       rotation=20, ha="right")
    ax.set_ylabel(ylabel)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.01),
              ncol=2, columnspacing=2.5, handletextpad=0.5)


def fig1_example(df_raw):
    """Concrete anchor: one artwork, one condition, one prompt, scored three
    times by each model. Shows what run-to-run (in)consistency looks like."""
    aid, cond, prompt = "TEST-005", "A", 5
    sub = df_raw[(df_raw["artwork_id"] == aid) & (df_raw["condition"] == cond)
                 & (df_raw["review_prompt"] == prompt) & (df_raw["is_error"] == False)]  # noqa: E712
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    for m in MODEL_ORDER:
        s = sub[sub["model"] == m].sort_values("run")
        ax.plot(s["run"], s["overall"], marker="o", markersize=7, linewidth=2.2,
                color=MODEL_COLOR[m], label=MODEL_LABEL[m])
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Review run (identical inputs)")
    ax.set_ylabel("Overall score (0 to 100)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=10.5, loc="lower left", ncol=2)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig1_example_runs.png", bbox_inches="tight")
    plt.close(fig)


def fig1_decision(grp):
    rate = (grp.groupby(["review_prompt", "model"])["unanimous"].mean() * 100)
    v4 = [rate[(4, m)] for m in MODEL_ORDER]
    v5 = [rate[(5, m)] for m in MODEL_ORDER]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    grouped_bars(ax, v4, v5, "Unanimous decision rate (%)", "{:.1f}")
    ax.set_ylim(0, 100)
    ax.axhspan(0, 0, color="none")
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig2_decision_consistency.png", bbox_inches="tight")
    plt.close(fig)


def fig2_artwork(grp):
    # 8 least-consistent artworks by overall unanimous rate, recomputed from
    # the data (the set can shift as models are added); ascending order.
    per_art = grp.groupby("artwork_id")["unanimous"].mean().sort_values()
    eight = list(per_art.index[:8])
    M = (grp[grp["artwork_id"].isin(eight)]
         .groupby(["artwork_id", "model"])["unanimous"].mean()
         .unstack("model").reindex(index=eight, columns=MODEL_ORDER) * 100)
    fig, ax = plt.subplots(figsize=(9.6, 5.0))
    im = ax.imshow(M.values, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(MODEL_ORDER)))
    ax.set_xticklabels([MODEL_LABEL[m] for m in MODEL_ORDER], fontsize=9,
                       rotation=20, ha="right")
    def art_num(a):
        return a.replace("TEST-0", "").replace("TEST-", "")
    ax.set_yticks(range(len(eight)))
    ax.set_yticklabels([f"{art_num(a)}  ·  {GENRE.get(a,'')}" for a in eight],
                       fontsize=10)
    for i in range(len(eight)):
        for j in range(len(MODEL_ORDER)):
            v = M.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=10,
                    color="#1a1a1a")
    ax.set_xticks(np.arange(-.5, len(MODEL_ORDER), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(eight), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.grid(which="major", visible=False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("Unanimous decision rate (%)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig3_artwork_consistency.png", bbox_inches="tight")
    plt.close(fig)


def fig3_score(grp):
    # Average score swing = mean, across a model's groups, of (max - min) of
    # the three run scores. Plain-language stand-in for within-group spread.
    rng = grp.groupby(["review_prompt", "model"])["srange"].mean()
    v4 = [rng[(4, m)] for m in MODEL_ORDER]
    v5 = [rng[(5, m)] for m in MODEL_ORDER]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    grouped_bars(ax, v4, v5,
                 "Average score swing across three runs (points)", "{:.1f}")
    ax.set_ylim(0, max(v4 + v5) * 1.25)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig4_score_consistency.png", bbox_inches="tight")
    plt.close(fig)


# ---- Section 4.2 context figures ----

CTX_ORDER = ["A", "B", "C", "D", "E-related", "E-unrelated"]
CTX_LABEL = {"A": "A\nartwork\nonly", "B": "B\n+desc", "C": "C\n+artist",
             "D": "D\n+desc\n+artist", "E-related": "E\nrelated\ncollector",
             "E-unrelated": "E\nunrelated\ncollector"}


def _ctx_frame(df_raw):
    d = df_raw[df_raw["is_error"] == False].copy()  # noqa: E712
    d["preference_variant"] = d["preference_variant"].fillna("none")
    d["ctx"] = d.apply(
        lambda r: f"E-{r['preference_variant']}" if r["condition"] == "E"
        else r["condition"], axis=1)
    return d


def fig5_context(df_raw):
    d = _ctx_frame(df_raw)
    score = [d[d.ctx == c]["overall"].mean() for c in CTX_ORDER]
    acq = [100 * (d[d.ctx == c]["decision"] == "ACQUIRE").mean() for c in CTX_ORDER]
    # highlight the unrelated-collector collapse in red, everything else slate
    colors = ["#4c6fa5"] * 5 + ["#c2453f"]
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.7))
    for ax, vals, title in ((axes[0], score, "Mean overall score"),
                            (axes[1], acq, "ACQUIRE rate (%)")):
        bars = ax.bar(range(len(CTX_ORDER)), vals, color=colors, width=0.72)
        for r, v in zip(bars, vals):
            ax.annotate(f"{v:.0f}", (r.get_x() + r.get_width() / 2, v),
                        ha="center", va="bottom", fontsize=10,
                        xytext=(0, 2), textcoords="offset points")
        ax.set_xticks(range(len(CTX_ORDER)))
        ax.set_xticklabels([CTX_LABEL[c] for c in CTX_ORDER], fontsize=8.5)
        ax.set_ylim(0, 100)
        ax.set_title(title, fontsize=12)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig5_context_effects.png", bbox_inches="tight")
    plt.close(fig)


def fig6_preference(df_raw):
    d = _ctx_frame(df_raw)
    aid = "TEST-001"
    sub = d[d.artwork_id == aid]
    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    for m in MODEL_ORDER:
        y = [sub[(sub.model == m) & (sub.ctx == c)]["overall"].mean() for c in CTX_ORDER]
        ax.plot(range(len(CTX_ORDER)), y, marker="o", markersize=7, linewidth=2.2,
                color=MODEL_COLOR[m], label=MODEL_LABEL[m])
    ax.axvspan(4.5, 5.5, color="#c2453f", alpha=0.07)
    ax.set_xticks(range(len(CTX_ORDER)))
    ax.set_xticklabels([CTX_LABEL[c] for c in CTX_ORDER], fontsize=9)
    ax.set_ylabel("Mean overall score (0 to 100)")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=10, loc="lower left", ncol=2)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig6_preference_example.png", bbox_inches="tight")
    plt.close(fig)


def fig7_prompt(df_raw):
    d = df_raw[df_raw["is_error"] == False]  # noqa: E712
    score = d.groupby(["review_prompt", "model"])["overall"].mean()
    acqr = d.groupby(["review_prompt", "model"])["decision"].apply(
        lambda s: 100 * (s == "ACQUIRE").mean())
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.7))
    grouped_bars(axes[0], [score[(4, m)] for m in MODEL_ORDER],
                 [score[(5, m)] for m in MODEL_ORDER], "Mean overall score", "{:.0f}")
    axes[0].set_ylim(0, 100)
    grouped_bars(axes[1], [acqr[(4, m)] for m in MODEL_ORDER],
                 [acqr[(5, m)] for m in MODEL_ORDER], "ACQUIRE rate (%)", "{:.0f}")
    axes[1].set_ylim(0, 100)
    for ax in axes:
        ax.set_xticklabels([MODEL_LABEL[m] for m in MODEL_ORDER],
                           fontsize=8.5, rotation=18, ha="right")
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig7_prompt_effects.png", bbox_inches="tight")
    plt.close(fig)


FAMILY_COLOR = {"GPT": "#2b5d8a", "Gemini": "#c17a30", "Claude": "#3f8f5e"}
FAMILY_OF = {"gpt-5": "GPT", "gpt-5-mini": "GPT",
             "gemini-2.5-flash": "Gemini", "gemini-3-flash-preview": "Gemini",
             "claude-haiku-4-5": "Claude", "claude-sonnet-4-6": "Claude"}
TIER_MARKER = {"gpt-5-mini": "o", "gemini-2.5-flash": "o", "claude-haiku-4-5": "o",  # economic
               "gpt-5": "s", "gemini-3-flash-preview": "s", "claude-sonnet-4-6": "s"}  # frontier
# per-model label offset (points) to keep the six labels from colliding
LABEL_DXY = {"gpt-5": (0, -20), "gpt-5-mini": (0, 12),
             "gemini-2.5-flash": (0, 12), "gemini-3-flash-preview": (0, 12),
             "claude-haiku-4-5": (0, 12), "claude-sonnet-4-6": (0, -20)}


def fig8_temperament(df_raw, grp):
    d = df_raw[df_raw["is_error"] == False]  # noqa: E712
    mean = d.groupby("model")["overall"].mean()
    swing = grp.groupby("model")["srange"].mean()
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    for m in MODEL_ORDER:
        ax.scatter(mean[m], swing[m], s=190, color=FAMILY_COLOR[FAMILY_OF[m]],
                   marker=TIER_MARKER[m], edgecolor="white", linewidth=1.5, zorder=3)
        ax.annotate(MODEL_LABEL[m], (mean[m], swing[m]),
                    xytext=LABEL_DXY.get(m, (0, 12)), textcoords="offset points",
                    ha="center", fontsize=10)
    ax.set_xlabel("Mean overall score  (harsher ←      → more generous)")
    ax.set_ylabel("Score swing across runs  (steadier ↓      ↑ noisier)")
    mvals, svals = [mean[m] for m in MODEL_ORDER], [swing[m] for m in MODEL_ORDER]
    ax.set_xlim(min(mvals) - 5, max(mvals) + 5)
    ax.set_ylim(min(svals) - 1.2, max(svals) + 1.6)
    from matplotlib.lines import Line2D
    legend = [Line2D([0], [0], marker="o", color="w", markerfacecolor="#888",
                     markersize=11, label="Economic tier"),
              Line2D([0], [0], marker="s", color="w", markerfacecolor="#888",
                     markersize=11, label="Frontier tier")]
    legend += [Line2D([0], [0], marker="o", color="w",
                      markerfacecolor=FAMILY_COLOR[fam], markersize=11,
                      label=f"{fam} family") for fam in ("GPT", "Gemini", "Claude")]
    ax.legend(handles=legend, frameon=False, fontsize=9.5, loc="upper right", ncol=2)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig8_temperament.png", bbox_inches="tight")
    plt.close(fig)


def fig9_test012(df_raw):
    """The literal-brief reversal: one work's acquisition rate across the six
    contexts, where the aligned collector crashes below the mismatched one."""
    d = _ctx_frame(df_raw)
    sub = d[d.artwork_id == "TEST-012"]
    acq = [100 * (sub[sub.ctx == c]["decision"] == "ACQUIRE").mean() for c in CTX_ORDER]
    colors = ["#4c6fa5"] * 4 + ["#c2453f", "#4c6fa5"]  # highlight E-related crash
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    bars = ax.bar(range(len(CTX_ORDER)), acq, color=colors, width=0.72)
    for r, v in zip(bars, acq):
        ax.annotate(f"{v:.0f}", (r.get_x() + r.get_width() / 2, v), ha="center",
                    va="bottom", fontsize=10, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(range(len(CTX_ORDER)))
    ax.set_xticklabels([CTX_LABEL[c] for c in CTX_ORDER], fontsize=8.5)
    ax.set_ylabel("ACQUIRE rate (%)")
    ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig9_test012_reversal.png", bbox_inches="tight")
    plt.close(fig)


def fig10_invented(df_raw):
    """Invented-buyer rate in no-preference reviews, by model and prompt."""
    import re
    r = pd.read_csv(INFO / "rationales.csv").dropna(subset=["rational"])
    r["prompt"] = r["experiment"].map({"experiment-1": 4, "experiment-2": 4,
                                       "experiment-3": 5, "experiment-4": 5,
                                       "experiment-5": 4, "experiment-6": 5})
    nopref = r[r.condition.isin(["A", "B", "C", "D"])].copy()
    invent = re.compile(
        r"(?:would (?:suit|appeal|fit|resonate)|for a collect|a collector who|"
        r"the right (?:collector|buyer)|find(?:s)? (?:its|an|a) (?:audience|buyer|home|market)|"
        r"market appeal|collector base|right audience)", re.I)
    nopref["invents"] = nopref["rational"].str.contains(invent)
    rate = nopref.groupby(["prompt", "model"])["invents"].mean() * 100
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    grouped_bars(ax, [rate[(4, m)] for m in MODEL_ORDER],
                 [rate[(5, m)] for m in MODEL_ORDER],
                 "Reviews inventing a collector (%)", "{:.0f}")
    ax.set_ylim(0, max(rate) * 1.25)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig10_invented_buyer.png", bbox_inches="tight")
    plt.close(fig)


def main():
    FIGDIR.mkdir(parents=True, exist_ok=True)
    grp = load_groups()
    df_raw = pd.read_csv(INFO / "reviews.csv")
    print(f"complete groups: {len(grp)}")
    fig1_example(df_raw)
    fig1_decision(grp)
    fig2_artwork(grp)
    fig3_score(grp)
    fig5_context(df_raw)
    fig6_preference(df_raw)
    fig7_prompt(df_raw)
    fig8_temperament(df_raw, grp)
    fig9_test012(df_raw)
    fig10_invented(df_raw)
    for p in sorted(FIGDIR.glob("*.png")):
        print(f"  wrote {p.relative_to(REPO_ROOT)}  ({p.stat().st_size//1024} KB)")


if __name__ == "__main__":
    main()
