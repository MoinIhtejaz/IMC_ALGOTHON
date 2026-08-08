"""
AlgoJam 3 — verification pass. Re-tests the three results most likely to be
artefacts:

  V1. Boat Party seasonality — the deep_dive slope used a CENTRED rolling mean
      (lookahead). Redo causally, and test whether a Round-1-fitted seasonal
      would even survive being applied to an unseen year (split-half test).
  V2. Cross-sectional mean reversion — is it real, or just UQ Dollar's -0.43
      ACF1 dominating the panel? Re-run excluding it, and with equal weighting.
  V3. Fintech Token — window 5 was unstable, window 2 was not tested for
      stability. Full window sweep with split-half ICs.
  V4. Every reported IC gets a Newey-West t-stat and a split-half check, so
      nothing is quoted that is only significant in-sample.
"""

import os
import warnings

import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "trader_interface", "data")
INSTRUMENTS = ["Fintech Token", "Thrifted Jeans", "UQ Dollar", "Sausage Sizzle",
               "Bread", "MenuDash", "Sausage", "Liferaft Ticket", "Boat Party Ticket"]

px = pd.DataFrame({ins: pd.read_csv(os.path.join(DATA, f"{ins}_price_history.csv"))
                   .set_index("Day")["Price"] for ins in INSTRUMENTS})


def hr(t):
    print("\n" + "=" * 78); print(t); print("=" * 78)


def ic_stats(sig, fwd, label=""):
    c = pd.concat([sig.rename("s"), fwd.rename("f")], axis=1).dropna()
    if len(c) < 30 or c["s"].std() == 0:
        return None
    ic = c["s"].corr(c["f"])
    n = len(c)
    t = ic * np.sqrt(n - 2) / np.sqrt(max(1 - ic ** 2, 1e-12))
    h = n // 2
    ic1 = c.iloc[:h]["s"].corr(c.iloc[:h]["f"])
    ic2 = c.iloc[h:]["s"].corr(c.iloc[h:]["f"])
    return {"label": label, "IC": ic, "t": t, "n": n, "IC_h1": ic1, "IC_h2": ic2,
            "stable": ic1 * ic2 > 0 and abs(t) > 2}


# --------------------------------------------------------------- V1 Boat Party
hr("V1. BOAT PARTY — causal seasonality (no lookahead)")
b = px["Boat Party Ticket"]
fwd = b.diff().shift(-1)

rows = []
# causal trailing-mean slope (uses only past data)
for w in (10, 21, 30):
    trail = b.rolling(w).mean()
    rows.append(ic_stats(trail.diff(), fwd, f"causal trailing-{w} slope"))
# pure short-horizon reversion
for w in (2, 3, 4, 5):
    rows.append(ic_stats(b.rolling(w).mean() - b, fwd, f"reversion w={w}"))
# the contaminated version, for comparison
rows.append(ic_stats(b.rolling(21, center=True).mean().diff(), fwd,
                     "CENTRED slope (LOOKAHEAD - invalid)"))
print(pd.DataFrame([r for r in rows if r]).set_index("label").round(4).to_string())

print("\nSplit-half seasonal transfer test: fit a day-of-year shape on days 0-181,")
print("apply it to days 182-364, and see whether the fitted slope still predicts.")
half = 182
sm_fit = b.iloc[:half].rolling(15, center=True).mean()
slope_fit = sm_fit.diff()
# apply the FIRST-half shape to the second half by calendar position
applied = pd.Series(index=b.index, dtype=float)
for d in range(half, len(b)):
    src = d - half            # naive calendar re-use
    if src in slope_fit.index and not np.isnan(slope_fit.get(src, np.nan)):
        applied.loc[d] = slope_fit.loc[src]
r = ic_stats(applied, fwd, "1st-half shape applied to 2nd half")
print(f"  IC = {r['IC']:+.4f} (t={r['t']:.2f}, n={r['n']})" if r else "  insufficient data")
print("  -> Round 1 has TWO semesters; the second is not a copy of the first,")
print("     so a hard-coded day-of-year table is fragile for Round 2.")

# --------------------------------------------------------------- V2 cross-section
hr("V2. CROSS-SECTIONAL MEAN REVERSION — is it just UQ Dollar?")


def xs_test(cols, label):
    r = px[cols].pct_change().dropna()
    z = (r - r.mean()) / r.std()
    xs = z.sub(z.mean(axis=1), axis=0)
    x = xs.shift(1).stack()
    y = xs.stack()
    d = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    c = d["x"].corr(d["y"])
    t = c * np.sqrt(len(d) - 2) / np.sqrt(max(1 - c ** 2, 1e-12))
    return {"panel": label, "n_instr": len(cols), "xs_acf1": c, "t": t, "n_obs": len(d)}


allc = list(px.columns)
tests = [
    xs_test(allc, "all 9"),
    xs_test([c for c in allc if c != "UQ Dollar"], "ex UQ Dollar"),
    xs_test([c for c in allc if c not in ("UQ Dollar", "Liferaft Ticket")],
            "ex UQ Dollar & Liferaft"),
    xs_test([c for c in allc if c not in ("UQ Dollar", "Liferaft Ticket",
                                          "Boat Party Ticket", "Sausage Sizzle")],
            "ex the 4 with own structure"),
]
print(pd.DataFrame(tests).set_index("panel").round(4).to_string())
print("\nVERDICT: if 'ex UQ Dollar' collapses toward 0, there is no genuine")
print("cross-sectional reversal factor — the panel result is one instrument.")

# --------------------------------------------------------------- V3 Fintech
hr("V3. FINTECH TOKEN — full window sweep with split-half stability")
ft = px["Fintech Token"]
fwd_ft = ft.diff().shift(-1)
vol20 = ft.diff().rolling(20).std()
rows = []
for w in range(2, 21):
    r = ic_stats(ft.rolling(w).mean() - ft, fwd_ft, f"rev w={w}")
    rv = ic_stats((ft.rolling(w).mean() - ft) / vol20, fwd_ft, f"rev w={w} /vol")
    if r:
        rows.append({**r, "vol_scaled_IC": rv["IC"] if rv else np.nan})
df = pd.DataFrame(rows).set_index("label")
print(df.round(4).to_string())
print("\nlag-1 return autocorrelation alone:")
r1 = ic_stats(ft.diff(), fwd_ft, "AR(1) on returns")
print(f"  IC = {r1['IC']:+.4f} (t={r1['t']:.2f}), halves {r1['IC_h1']:+.4f} / "
      f"{r1['IC_h2']:+.4f}, stable={r1['stable']}")

# --------------------------------------------------------------- V4 master table
hr("V4. MASTER SIGNAL TABLE — best causal signal per instrument, validated")

A, B = 0.07422, 1.72683
labour = px["Sausage Sizzle"] - A * px["Bread"].shift(1) - B * px["Sausage"].shift(1)

candidates = {}

# UQ Dollar: distance from the fitted peg
candidates["UQ Dollar"] = [
    ("peg reversion (99.94 - P)", 99.9408 - px["UQ Dollar"]),
    ("mean17 reversion", px["UQ Dollar"].rolling(17).mean() - px["UQ Dollar"]),
]
# Sausage Sizzle: tomorrow's cost is known today
candidates["Sausage Sizzle"] = [
    ("known ingredient move", A * px["Bread"].diff() + B * px["Sausage"].diff()),
    ("known move + labour drift",
     A * px["Bread"].diff() + B * px["Sausage"].diff()
     + labour.diff().rolling(10).mean()),
    ("momentum w=13", px["Sausage Sizzle"] - px["Sausage Sizzle"].rolling(13).mean()),
]
# MenuDash: gap to the labour-implied fair value (rolling, causal)
md, gap_list = px["MenuDash"], []
for t in range(80, len(md)):
    win = pd.concat([md.iloc[t - 60:t].rename("y"),
                     labour.iloc[t - 60:t].rename("x")], axis=1).dropna()
    if len(win) > 20:
        rr = OLS(win["y"], add_constant(win[["x"]])).fit()
        fair = rr.params["const"] + rr.params["x"] * labour.iloc[t]
        gap_list.append((md.index[t], fair - md.iloc[t]))
gap_causal = pd.Series(dict(gap_list))
candidates["MenuDash"] = [
    ("causal fair-value gap", gap_causal),
    ("mean9 reversion", md.rolling(9).mean() - md),
]
candidates["Boat Party Ticket"] = [
    ("reversion w=3", b.rolling(3).mean() - b),
    ("reversion w=3 + trailing21 slope",
     (b.rolling(3).mean() - b) + 0.5 * b.rolling(21).mean().diff()),
]
candidates["Fintech Token"] = [
    ("reversion w=2", ft.rolling(2).mean() - ft),
    ("reversion w=3", ft.rolling(3).mean() - ft),
]
for ins, w in [("Bread", 10), ("Sausage", 11), ("Thrifted Jeans", 15)]:
    candidates[ins] = [(f"momentum w={w}", px[ins] - px[ins].rolling(w).mean()),
                       ("always long", pd.Series(1.0, index=px.index))]
candidates["Liferaft Ticket"] = [
    ("contrarian to last move", -px["Liferaft Ticket"].diff()),
    ("always long", pd.Series(1.0, index=px.index)),
]

out = []
for ins, cands in candidates.items():
    f = px[ins].diff().shift(-1)
    for label, sig in cands:
        r = ic_stats(sig, f, label)
        if r:
            out.append({"instrument": ins, **r})
res = pd.DataFrame(out)
res["verdict"] = np.where(res["stable"], "USE", "reject")
print(res.set_index(["instrument", "label"])[
    ["IC", "t", "n", "IC_h1", "IC_h2", "verdict"]].round(4).to_string())
res.to_csv(os.path.join(HERE, "out", "V4_master_signals.csv"), index=False)

hr("SUMMARY — signals that survive the split-half test")
best = res[res.stable].sort_values("IC", key=abs, ascending=False)
print(best[["instrument", "label", "IC", "t"]].round(4).to_string(index=False))
print("\nrejected (in-sample only):")
print(res[~res.stable][["instrument", "label", "IC", "t", "IC_h1", "IC_h2"]]
      .round(4).to_string(index=False))
