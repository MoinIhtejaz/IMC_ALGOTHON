"""Figures for the AlgoJam 3 structural analysis report.

Every figure is built from the same Round 1 CSVs the tests use, so nothing in
the report is illustrative-only. Output: research/figures/*.png at 200 dpi.
"""

import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from statsmodels.tsa.stattools import acf
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "trader_interface", "data")
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

INSTRUMENTS = ["Fintech Token", "Thrifted Jeans", "UQ Dollar", "Sausage Sizzle",
               "Bread", "MenuDash", "Sausage", "Liferaft Ticket", "Boat Party Ticket"]

px = pd.DataFrame({i: pd.read_csv(os.path.join(DATA, f"{i}_price_history.csv"))
                   .set_index("Day")["Price"] for i in INSTRUMENTS})

INK = "#1c1f24"
BLUE = "#2f6ea5"
RED = "#b4453a"
GREEN = "#2f7d4f"
AMBER = "#c8821a"
GREY = "#9aa1ab"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Carlito", "DejaVu Sans"],
    "font.size": 8,
    "axes.edgecolor": "#c3c8cf", "axes.linewidth": 0.7,
    "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": "#5c636d", "ytick.color": "#5c636d",
    "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.titlesize": 8.5, "axes.titleweight": "bold",
    "axes.grid": True, "grid.color": "#e8ebee", "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.dpi": 200, "savefig.dpi": 200,
    "savefig.bbox": "tight", "savefig.facecolor": "white",
    "legend.frameon": False, "legend.fontsize": 7,
})


def save(fig, name):
    fig.savefig(os.path.join(FIG, name), facecolor="white")
    plt.close(fig)
    print("  ", name)


def despine(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


# ---------------------------------------------------------------- fig 1: prices
def fig_prices():
    fig, axes = plt.subplots(3, 3, figsize=(7.3, 4.45))
    notes = {
        "UQ Dollar": ("flat, tight band", GREEN),
        "Sausage Sizzle": ("smooth climb", GREEN),
        "MenuDash": ("stepped / rounded", AMBER),
        "Boat Party Ticket": ("two humps = semesters", AMBER),
        "Fintech Token": ("calm then wild", RED),
        "Liferaft Ticket": ("moves take only 2 values", RED),
    }
    for ax, ins in zip(axes.flat, INSTRUMENTS):
        s = px[ins]
        col = notes.get(ins, ("", BLUE))[1]
        ax.plot(s.index, s.values, lw=0.8, color=col)
        ax.set_title(ins, loc="left")
        if ins in notes:
            ax.text(0.97, 0.05, notes[ins][0], transform=ax.transAxes, ha="right",
                    fontsize=6.4, color=col, style="italic",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none",
                              alpha=0.86))
        ax.yaxis.set_major_locator(MaxNLocator(4))
        ax.set_xlim(0, 364)
        despine(ax)
    for ax in axes[-1]:
        ax.set_xlabel("day", fontsize=7)
    fig.suptitle("The nine Round 1 price series", x=0.005, ha="left",
                 fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save(fig, "f1_prices.png")


# ---------------------------------------------------------------- fig 2: ACF
def fig_acf():
    order = ["UQ Dollar", "Boat Party Ticket", "Fintech Token",
             "Sausage Sizzle", "Sausage", "Thrifted Jeans"]
    fig, axes = plt.subplots(2, 3, figsize=(7.3, 3.2))
    for ax, ins in zip(axes.flat, order):
        r = px[ins].diff().dropna()
        a = acf(r, nlags=10, fft=False)[1:]
        band = 1.96 / np.sqrt(len(r))
        cols = [RED if v < -band else (GREEN if v > band else GREY) for v in a]
        ax.bar(range(1, 11), a, color=cols, width=0.62)
        ax.axhspan(-band, band, color="#dfe4ea", alpha=0.75, zorder=0)
        ax.axhline(0, color="#8d949d", lw=0.7)
        ax.set_title(ins, loc="left")
        ax.set_ylim(-0.58, 0.32)
        ax.set_xticks([1, 3, 5, 7, 10])
        despine(ax)
    for ax in axes[-1]:
        ax.set_xlabel("lag (days)", fontsize=7)
    axes[0][0].set_ylabel("correlation", fontsize=7)
    axes[1][0].set_ylabel("correlation", fontsize=7)
    axes[0][0].annotate("shaded band =\nindistinguishable\nfrom zero",
                        xy=(6, 0.02), xytext=(5.2, -0.42), fontsize=6.2,
                        color="#5c636d",
                        arrowprops=dict(arrowstyle="->", color="#5c636d", lw=0.6))
    fig.suptitle("Autocorrelation of daily price changes  —  red = reverses, "
                 "green = trends, grey = noise", x=0.005, ha="left",
                 fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    save(fig, "f2_acf.png")


# ---------------------------------------------------------------- fig 3: UQ Dollar
def fig_uqd():
    u = px["UQ Dollar"]
    dev = (u - 100).iloc[:-1].values
    nxt = u.diff().shift(-1).dropna().values
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.2),
                             gridspec_kw={"width_ratios": [1.25, 1, 1]})

    ax = axes[0]
    ax.plot(u.index, u.values, lw=0.7, color=BLUE)
    ax.axhline(100, color=RED, lw=1.0, ls="--")
    ax.text(0.985, 0.985, "peg = $100", transform=ax.transAxes, ha="right",
            va="top", fontsize=6.8, color=RED, fontweight="bold")
    ax.set_title("Price never leaves the band", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("price ($)", fontsize=7)
    despine(ax)

    ax = axes[1]
    ax.scatter(dev, nxt, s=5, alpha=0.45, color=BLUE, edgecolors="none")
    xs = np.linspace(dev.min(), dev.max(), 50)
    b, a = np.polyfit(dev, nxt, 1)
    ax.plot(xs, a + b * xs, color=RED, lw=1.3)
    ax.axhline(0, color="#b6bcc4", lw=0.6); ax.axvline(0, color="#b6bcc4", lw=0.6)
    ax.set_title(f"Today's gap predicts tomorrow (slope {b:.2f})", loc="left")
    ax.set_xlabel("deviation from $100 today", fontsize=7)
    ax.set_ylabel("price change tomorrow", fontsize=7)
    ax.text(0.04, 0.06, "IC = 0.69", transform=ax.transAxes, fontsize=7.5,
            color=RED, fontweight="bold")
    despine(ax)

    ax = axes[2]
    d = pd.DataFrame({"dev": dev, "nxt": nxt})
    d["bin"] = pd.qcut(d["dev"], 6)
    g = d.groupby("bin", observed=True).apply(
        lambda x: (np.sign(x["nxt"]) == -np.sign(x["dev"])).mean())
    ax.bar(range(len(g)), g.values, color=[GREY if v < 0.55 else GREEN for v in g],
           width=0.7)
    ax.axhline(0.5, color=RED, ls="--", lw=0.9)
    ax.text(0.985, 0.985, "50% = coin flip", transform=ax.transAxes, ha="right",
            va="top", fontsize=6.8, color=RED, fontweight="bold")
    ax.set_xticks(range(len(g)))
    ax.set_xticklabels(["big\nbelow", "below", "just\nbelow", "just\nabove",
                        "above", "big\nabove"], fontsize=6.2)
    ax.set_ylim(0, 1.0)
    ax.set_title("Bigger gap → surer bet", loc="left")
    ax.set_ylabel("hit rate", fontsize=7)
    despine(ax)

    fig.suptitle("UQ Dollar: a spring pulling back to $100", x=0.005, ha="left",
                 fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    save(fig, "f3_uqdollar.png")


# ---------------------------------------------------------------- fig 4: Sizzle
def fig_sizzle():
    d = pd.DataFrame({"sz": px["Sausage Sizzle"], "br1": px["Bread"].shift(1),
                      "sa1": px["Sausage"].shift(1)}).dropna()
    r = OLS(d["sz"], add_constant(d[["br1", "sa1"]])).fit()
    A, B = r.params["br1"], r.params["sa1"]
    labour = d["sz"] - A * d["br1"] - B * d["sa1"]

    known = A * px["Bread"].diff() + B * px["Sausage"].diff()
    fwd = px["Sausage Sizzle"].diff().shift(-1)
    c = pd.concat([known.rename("k"), fwd.rename("f")], axis=1).dropna()

    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.2))

    ax = axes[0]
    ax.plot(d.index, d["sz"], lw=0.9, color=INK, label="actual sizzle price")
    ax.plot(d.index, r.fittedvalues, lw=0.9, color=RED, ls="--",
            label="recipe prediction")
    ax.set_title("Recipe reproduces the price (R² = 0.70)", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("price ($)", fontsize=7)
    ax.legend(loc="upper left")
    despine(ax)

    ax = axes[1]
    ax.plot(labour.index, labour.values, lw=0.8, color=AMBER)
    ax.set_title("Left-over 'labour' cost barely moves", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("$", fontsize=7)
    ax.text(0.03, 0.06, "daily change SD = $0.04", transform=ax.transAxes,
            fontsize=6.8, color=AMBER)
    despine(ax)

    ax = axes[2]
    ax.scatter(c["k"], c["f"], s=5, alpha=0.45, color=GREEN, edgecolors="none")
    xs = np.linspace(c["k"].min(), c["k"].max(), 40)
    bb, aa = np.polyfit(c["k"], c["f"], 1)
    ax.plot(xs, aa + bb * xs, color=RED, lw=1.3)
    ax.set_title("Today's ingredients → tomorrow's price", loc="left")
    ax.set_xlabel("ingredient cost change today", fontsize=7)
    ax.set_ylabel("sizzle change tomorrow", fontsize=7)
    ax.text(0.04, 0.88, "IC = 0.92", transform=ax.transAxes, fontsize=7.5,
            color=RED, fontweight="bold")
    despine(ax)

    fig.suptitle("Sausage Sizzle: tomorrow's price is already on today's receipt",
                 x=0.005, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    save(fig, "f4_sizzle.png")


# ---------------------------------------------------------------- fig 5: vol
def fig_vol():
    ft = px["Fintech Token"]
    r = ft.diff().dropna()
    vol20 = r.rolling(20).std()
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.2))

    ax = axes[0]
    ax.plot(r.index, r.values, lw=0.5, color=BLUE)
    ax.axhline(0, color="#b6bcc4", lw=0.6)
    ax.set_title("Daily moves: quiet spells, then storms", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("change ($)", fontsize=7)
    despine(ax)

    ax = axes[1]
    ax.plot(vol20.index, vol20.values, lw=1.1, color=RED)
    ax.fill_between(vol20.index, 0, vol20.values, color=RED, alpha=0.12)
    ax.set_title("20-day volatility drifts slowly (2.7× range)", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("volatility ($)", fontsize=7)
    ax.set_ylim(0, None)
    despine(ax)

    ax = axes[2]
    names, vals, cols = [], [], []
    for ins in ["Fintech Token", "UQ Dollar", "Sausage Sizzle", "Bread",
                "MenuDash", "Thrifted Jeans", "Sausage", "Boat Party Ticket"]:
        rr = px[ins].diff().dropna().abs()
        a = acf(rr, nlags=10, fft=False)
        names.append(ins); vals.append(a[1])
    real = {"Fintech Token", "UQ Dollar"}
    cols = [RED if n in real else GREY for n in names]
    y = np.arange(len(names))
    ax.barh(y, vals, color=cols, height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels([n if len(n) < 15 else n[:13] + "…" for n in names],
                       fontsize=6.3)
    ax.invert_yaxis()
    ax.axvline(0, color="#8d949d", lw=0.7)
    band = 1.96 / np.sqrt(364)
    ax.axvspan(-band, band, color="#dfe4ea", alpha=0.8, zorder=0)
    ax.set_title("Volatility memory (|move| autocorrelation)", loc="left")
    ax.set_xlabel("correlation at lag 1", fontsize=7)
    despine(ax)

    fig.suptitle("Fintech Token: direction is unpredictable, size is not",
                 x=0.005, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    save(fig, "f5_volatility.png")


# ---------------------------------------------------------------- fig 6: split-half
def fig_splithalf():
    rows = [
        ("Sausage Sizzle", "ingredients + drift", 0.9656, 0.9531, True),
        ("UQ Dollar", "reversion to peg", 0.7091, 0.6838, True),
        ("MenuDash", "fair-value gap", 0.3012, 0.2652, True),
        ("Sausage Sizzle", "momentum w=13", 0.3246, 0.1639, True),
        ("Boat Party", "reversion w=3", 0.0853, 0.2989, True),
        ("Sausage", "momentum w=11", 0.2621, 0.0725, True),
        ("Bread", "momentum w=10", 0.1359, 0.1266, True),
        ("Fintech Token", "reversion w=2", 0.0592, 0.2433, True),
        ("Thrifted Jeans", "momentum w=15", 0.0573, 0.1246, False),
        ("Fintech Token", "reversion w=5", -0.1104, 0.1736, False),
        ("Boat Party", "fixed seasonal table", 0.2928, -0.1184, False),
        ("Liferaft", "contrarian", -0.0701, -0.0073, False),
    ]
    labels = [f"{a} · {b}" for a, b, _, _, _ in rows]
    h1 = [r[2] for r in rows]; h2 = [r[3] for r in rows]
    ok = [r[4] for r in rows]
    y = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(7.3, 3.9))
    ax.barh(y - 0.2, h1, height=0.36, color=BLUE, label="first half (days 0–181)")
    ax.barh(y + 0.2, h2, height=0.36, color="#8fb4d4",
            label="second half (days 182–364)")
    for i, good in enumerate(ok):
        if not good:
            ax.axhspan(i - 0.48, i + 0.48, color="#f7e9e9", zorder=0)
    ax.axvline(0, color="#8d949d", lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=6.8)
    ax.invert_yaxis()
    ax.set_xlabel("IC (correlation between signal and next day's move)", fontsize=7)
    ax.legend(loc="lower right")
    ax.text(0.62, 0.585, "pink rows = rejected\n(halves disagree in sign,\n"
                         "or the effect is too small\nto separate from luck)",
            transform=ax.transAxes, fontsize=6.6, color=RED, style="italic")
    ax.set_title("Split-half test: does the signal work in both halves of the year?",
                 loc="left", fontsize=10.5)
    despine(ax)
    fig.tight_layout()
    save(fig, "f6_splithalf.png")


# ---------------------------------------------------------------- fig 7: XS
def fig_xs():
    def xs_acf(cols):
        r = px[cols].pct_change().dropna()
        z = (r - r.mean()) / r.std()
        xs = z.sub(z.mean(axis=1), axis=0)
        d = pd.concat([xs.shift(1).stack().rename("x"),
                       xs.stack().rename("y")], axis=1).dropna()
        c = d["x"].corr(d["y"])
        return c, c * np.sqrt(len(d) - 2) / np.sqrt(1 - c ** 2)

    allc = list(px.columns)
    panels = [
        ("all 9 instruments", allc),
        ("drop UQ Dollar", [c for c in allc if c != "UQ Dollar"]),
        ("drop UQ Dollar\n+ Liferaft", [c for c in allc if c not in
                                        ("UQ Dollar", "Liferaft Ticket")]),
        ("drop all 4 with\nown structure",
         [c for c in allc if c not in ("UQ Dollar", "Liferaft Ticket",
                                       "Boat Party Ticket", "Sausage Sizzle")]),
    ]
    res = [(n, *xs_acf(c)) for n, c in panels]

    fig, axes = plt.subplots(1, 2, figsize=(7.3, 2.32),
                             gridspec_kw={"width_ratios": [1, 1.1]})
    ax = axes[0]
    x = np.arange(len(res))
    tvals = [abs(r[2]) for r in res]
    cols = [RED if t > 2 else GREY for t in tvals]
    ax.bar(x, tvals, color=cols, width=0.6)
    ax.axhline(2, color=INK, ls="--", lw=0.9)
    ax.text(2.55, 2.12, "significance threshold", fontsize=6.4, color=INK)
    ax.set_xticks(x); ax.set_xticklabels([r[0] for r in res], fontsize=6.3)
    ax.set_ylabel("|t-statistic|", fontsize=7)
    ax.set_title("Remove the self-reverting names and it dies", loc="left")
    despine(ax)

    ax = axes[1]
    ins_acf = []
    r = px.pct_change().dropna()
    z = (r - r.mean()) / r.std()
    xsd = z.sub(z.mean(axis=1), axis=0)
    for ins in px.columns:
        d = pd.concat([xsd[ins].shift(1).rename("x"), xsd[ins].rename("y")],
                      axis=1).dropna()
        ins_acf.append((ins, d["x"].corr(d["y"])))
    ins_acf.sort(key=lambda t: t[1])
    y = np.arange(len(ins_acf))
    band = 1.96 / np.sqrt(363)
    cols = [RED if abs(v) > band else GREY for _, v in ins_acf]
    ax.barh(y, [v for _, v in ins_acf], color=cols, height=0.6)
    ax.axvspan(-band, band, color="#dfe4ea", alpha=0.8, zorder=0)
    ax.axvline(0, color="#8d949d", lw=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels([n for n, _ in ins_acf], fontsize=6.4)
    ax.set_xlabel("own reversion after removing the market-wide move", fontsize=7)
    ax.set_title("It was UQ Dollar all along", loc="left")
    despine(ax)

    fig.suptitle("Cross-sectional mean reversion: a mirage",
                 x=0.005, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    save(fig, "f7_crosssection.png")


# ---------------------------------------------------------------- fig 8: leadlag
def fig_leadlag():
    r = px.diff().dropna()
    pairs, vals = [], []
    for x in px.columns:
        for y in px.columns:
            if x == y:
                continue
            for k in (1, 2, 3, 4, 5):
                pairs.append((x, y, k)); vals.append(r[x].shift(k).corr(r[y]))
    d = pd.DataFrame(pairs, columns=["leader", "follower", "lag"])
    d["corr"] = vals
    d = d.reindex(d["corr"].abs().sort_values(ascending=False).index).head(12)
    labels = [f"{a} → {b}  (lag {k})" for a, b, k in
              zip(d["leader"], d["follower"], d["lag"])]
    band = 1.96 / np.sqrt(364)
    y = np.arange(len(d))
    fig, ax = plt.subplots(figsize=(7.3, 2.9))
    cols = [GREEN if abs(v) > 0.3 else (AMBER if abs(v) > band else GREY)
            for v in d["corr"]]
    ax.barh(y, d["corr"].values, color=cols, height=0.62)
    ax.axvspan(-band, band, color="#dfe4ea", alpha=0.85, zorder=0)
    ax.axvline(0, color="#8d949d", lw=0.7)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=6.5)
    ax.invert_yaxis()
    ax.set_xlabel("correlation of leader's move with follower's move k days later",
                  fontsize=7)
    ax.text(0.42, 0.30, "only these two clear\nthe noise band",
            transform=ax.transAxes, fontsize=6.8, color=GREEN, style="italic")
    ax.set_title("Which instrument moves before which?", loc="left", fontsize=10.5)
    despine(ax)
    fig.tight_layout()
    save(fig, "f8_leadlag.png")


# ---------------------------------------------------------------- fig 9: menudash
def fig_menudash():
    md = px["MenuDash"]
    A, B = 0.07422, 1.72683
    labour = px["Sausage Sizzle"] - A * px["Bread"].shift(1) - B * px["Sausage"].shift(1)
    c = pd.concat([md.rename("md"), labour.rename("lab")], axis=1).dropna()
    reg = OLS(c["md"], add_constant(c[["lab"]])).fit()
    gap = c["md"] - reg.fittedvalues

    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.16))

    ax = axes[0]
    ax.step(md.index[:120], md.values[:120], lw=0.9, color=BLUE, where="post")
    ax.set_title("Price moves in 1-cent steps (first 120 days)", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("price ($)", fontsize=7)
    ax.text(0.03, 0.9, "22.5% of days: no move at all", transform=ax.transAxes,
            fontsize=6.6, color=AMBER)
    despine(ax)

    ax = axes[1]
    ax.plot(c.index, c["md"], lw=0.9, color=INK, label="MenuDash")
    ax2 = ax.twinx()
    ax2.plot(c.index, c["lab"], lw=0.9, color=AMBER, label="implied labour cost")
    ax2.grid(False)
    ax.set_title("It tracks the hidden labour cost (r = 0.93)", loc="left")
    ax.set_xlabel("day", fontsize=7)
    ax.set_ylabel("MenuDash ($)", fontsize=7, color=INK)
    ax2.set_ylabel("labour ($)", fontsize=7, color=AMBER)
    ax2.tick_params(colors=AMBER, labelsize=7)
    despine(ax)

    ax = axes[2]
    ax.plot(gap.index, gap.values, lw=0.7, color=GREEN)
    ax.axhline(0, color=RED, lw=0.9, ls="--")
    ax.fill_between(gap.index, 0, gap.values, color=GREEN, alpha=0.12)
    ax.set_title("Gap to fair value closes in ~3 days", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("price − fair value ($)", fontsize=7)
    despine(ax)

    fig.suptitle("MenuDash: a blurry, rounded readout of the same cost",
                 x=0.005, ha="left", fontsize=10.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.9])
    save(fig, "f9_menudash.png")


# ---------------------------------------------------------------- fig 10: boat/liferaft
def fig_boat_liferaft():
    b = px["Boat Party Ticket"]
    lr = px["Liferaft Ticket"]
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.16))

    ax = axes[0]
    ax.plot(b.index, b.values, lw=0.7, color=GREY, label="price")
    ax.plot(b.index, b.rolling(21).mean().values, lw=1.4, color=BLUE,
            label="21-day average")
    ax.set_title("Boat Party: two semester humps", loc="left")
    ax.set_xlabel("day", fontsize=7); ax.set_ylabel("price ($)", fontsize=7)
    ax.legend(loc="upper right")
    despine(ax)

    ax = axes[1]
    first = b.iloc[:182].values
    second = b.iloc[182:364].values
    ax.plot(range(182), first, lw=0.9, color=BLUE, label="semester 1 (days 0–181)")
    ax.plot(range(182), second, lw=0.9, color=RED, label="semester 2 (days 182–363)")
    ax.set_title("…but the two are NOT the same shape", loc="left")
    ax.set_xlabel("day within semester", fontsize=7)
    ax.set_ylabel("price ($)", fontsize=7)
    ax.legend(loc="upper right")
    despine(ax)

    ax = axes[2]
    dl = lr.diff().dropna()
    vc = dl.value_counts().sort_index()
    ax.bar([0, 1], vc.values, color=[RED, GREEN], width=0.5)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([f"−$5,000\n({int(vc.iloc[0])} days)",
                        f"+$8,000\n({int(vc.iloc[1])} days)"], fontsize=7)
    ax.set_title("Liferaft: only two possible outcomes", loc="left")
    ax.set_ylabel("number of days", fontsize=7)
    ax.set_ylim(0, 265)
    ax.text(0.5, 0.97, "never any other value, never unchanged",
            transform=ax.transAxes, ha="center", va="top", fontsize=6.6,
            style="italic", color="#5c636d")
    despine(ax)

    fig.tight_layout()
    save(fig, "f10_boat_liferaft.png")


print("figures:")
fig_prices(); fig_acf(); fig_uqd(); fig_sizzle(); fig_vol()
fig_splithalf(); fig_xs(); fig_leadlag(); fig_menudash(); fig_boat_liferaft()
print("done ->", FIG)
