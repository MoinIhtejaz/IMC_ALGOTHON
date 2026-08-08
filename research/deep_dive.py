"""
AlgoJam 3 — second-pass diagnostics.

Follow-ups on what structure_tests.py flagged:
  A. UQ Dollar    — is it an OU peg? what is the peg level, kappa, overshoot?
  B. Sausage Sizzle — exact recipe regression on lagged Bread/Sausage
  C. MenuDash     — rounding/tick structure, relation to implied labour
  D. Boat Party   — semester seasonality decomposition + overreaction size
  E. Fintech Token — jump/regime structure, GARCH vol persistence usefulness
  F. Bread/Sausage/Jeans — is "momentum" just drift? drift-removed IC
  G. Liferaft     — move distribution (game-theoretic, not price-driven)
  H. IC stability  — walk-forward IC in halves, with t-stats
  I. Signal PnL    — per-instrument gross PnL of the naive sign strategy
"""

import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "trader_interface", "data")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

INSTRUMENTS = ["Fintech Token", "Thrifted Jeans", "UQ Dollar", "Sausage Sizzle",
               "Bread", "MenuDash", "Sausage", "Liferaft Ticket", "Boat Party Ticket"]
LIMITS = {"Fintech Token": 100, "Thrifted Jeans": 800, "UQ Dollar": 650,
          "Sausage Sizzle": 3000, "Bread": 500, "MenuDash": 75000,
          "Sausage": 5000, "Liferaft Ticket": 1, "Boat Party Ticket": 1000}


def load():
    return pd.DataFrame({
        ins: pd.read_csv(os.path.join(DATA, f"{ins}_price_history.csv"))
               .set_index("Day")["Price"] for ins in INSTRUMENTS})


def hr(t):
    print("\n" + "=" * 78); print(t); print("=" * 78)


px = load()

# ------------------------------------------------------------------ A. UQ Dollar
hr("A. UQ DOLLAR — OU / peg structure")
u = px["UQ Dollar"]
du = u.diff().dropna()
X = add_constant(u.shift(1).dropna().loc[du.index])
m = OLS(du, X).fit()
kappa = -m.params.iloc[1]
peg = m.params.iloc[0] / kappa
print(f"dP_t = a + b*P_(t-1):  b = {m.params.iloc[1]:.4f} (t={m.tvalues.iloc[1]:.2f}), "
      f"kappa = {kappa:.4f}")
print(f"implied peg level     = {peg:.4f}   (sample mean {u.mean():.4f}, median {u.median():.4f})")
print(f"OU half-life          = {np.log(2)/kappa:.3f} days")
print(f"sigma of residual     = {m.resid.std():.4f}")
print(f"kappa > 1 means the price OVERSHOOTS the peg each day (ACF1 = {du.autocorr(1):.3f})")
print(f"\ndeviation from 100: mean {(u-100).mean():.4f}, std {(u-100).std():.4f}, "
      f"max |dev| {(u-100).abs().max():.3f}")
print(f"frac of days |dev| > 0.15 : {((u-100).abs() > 0.15).mean():.3f}")
print(f"frac of days |dev| > 0.50 : {((u-100).abs() > 0.50).mean():.3f}")

# how well does deviation predict the next move, by deviation bucket?
dev = (u - 100).iloc[:-1].values
nxt = u.diff().shift(-1).dropna().values
bins = pd.qcut(dev, 6, duplicates="drop")
tab = pd.DataFrame({"dev": dev, "next": nxt, "bin": bins}).groupby("bin", observed=True).agg(
    n=("next", "size"), mean_dev=("dev", "mean"), mean_next=("next", "mean"),
    hit=("next", lambda s: np.nan))
grp = pd.DataFrame({"dev": dev, "next": nxt, "bin": bins})
tab["hit_rate_vs_dev"] = grp.groupby("bin", observed=True).apply(
    lambda g: (np.sign(g["next"]) == -np.sign(g["dev"])).mean())
print("\nnext-day move by deviation bucket (hit = move opposes the deviation):")
print(tab[["n", "mean_dev", "mean_next", "hit_rate_vs_dev"]].round(4).to_string())

# multi-day reversion window comparison
print("\nIC of (peg - P_t) vs (mean_w - P_t) as predictor of next move:")
for name, sig in [("100 - P", 100 - u.iloc[:-1].values),
                  ("fitted peg - P", peg - u.iloc[:-1].values)]:
    print(f"  {name:>18}: IC = {np.corrcoef(sig, nxt)[0,1]:.4f}")
for w in (3, 5, 10, 17, 30):
    s = u.rolling(w).mean().shift(0)
    sig = (s - u).iloc[:-1].dropna()
    f = u.diff().shift(-1).loc[sig.index]
    print(f"  {'mean%d - P' % w:>18}: IC = {np.corrcoef(sig, f)[0,1]:.4f}")

# ------------------------------------------------------------------ B. Sizzle
hr("B. SAUSAGE SIZZLE — recipe regression")
d = pd.DataFrame({
    "sz": px["Sausage Sizzle"],
    "br1": px["Bread"].shift(1), "sa1": px["Sausage"].shift(1),
    "br0": px["Bread"], "sa0": px["Sausage"]}).dropna()
for label, cols in [("lag-1 bread+sausage", ["br1", "sa1"]),
                    ("same-day bread+sausage", ["br0", "sa0"]),
                    ("both", ["br1", "sa1", "br0", "sa0"])]:
    r = OLS(d["sz"], add_constant(d[cols])).fit()
    print(f"{label:>24}: R2 = {r.rsquared:.4f}  resid_sd = {r.resid.std():.4f}  "
          f"coefs = {dict(r.params.round(5))}")

r1 = OLS(d["sz"], add_constant(d[["br1", "sa1"]])).fit()
A, B = r1.params["br1"], r1.params["sa1"]
labour = d["sz"] - A * d["br1"] - B * d["sa1"]
print(f"\nfitted A (bread) = {A:.5f}, B (sausage) = {B:.5f}  "
      f"[algorithm.py priors: 0.07692, 1.76921]")
print(f"implied labour: mean {labour.mean():.4f}, sd {labour.std():.4f}, "
      f"daily-change sd {labour.diff().std():.4f}, ACF1 of change {labour.diff().autocorr(1):.4f}")
known = A * px["Bread"].diff() + B * px["Sausage"].diff()
fwd = px["Sausage Sizzle"].diff().shift(-1)
cc = pd.concat([known.rename("k"), fwd.rename("f")], axis=1).dropna()
print(f"IC of TODAY's known ingredient move vs TOMORROW's sizzle move: "
      f"{cc['k'].corr(cc['f']):.4f}  (n={len(cc)})")
print(f"predictable share of tomorrow's sizzle variance: {cc['k'].corr(cc['f'])**2:.3f}")

# ------------------------------------------------------------------ C. MenuDash
hr("C. MENUDASH — tick / rounding structure")
md = px["MenuDash"]
ticks = md.diff().dropna()
uniq = np.sort(np.unique(np.round(ticks.values, 6)))
print(f"unique daily changes ({len(uniq)}): {uniq[:15]} ... {uniq[-5:]}")
gcd_like = np.min(np.abs(uniq[uniq != 0]))
print(f"smallest non-zero move = {gcd_like:.4f}  (price grid appears to be 0.01)")
print(f"unchanged days: {(ticks == 0).mean():.3f}")
print(f"price range: {md.min():.2f} - {md.max():.2f}")
lab_full = px["Sausage Sizzle"] - A * px["Bread"].shift(1) - B * px["Sausage"].shift(1)
cmp = pd.concat([md.rename("md"), lab_full.rename("lab")], axis=1).dropna()
print(f"corr(MenuDash level, implied labour level)      = {cmp['md'].corr(cmp['lab']):.4f}")
print(f"corr(MenuDash change, implied labour change)    = "
      f"{cmp['md'].diff().corr(cmp['lab'].diff()):.4f}")
reg = OLS(cmp["md"], add_constant(cmp[["lab"]])).fit()
gap = cmp["md"] - reg.fittedvalues
fwd_md = md.diff().shift(-1).loc[gap.index]
g = pd.concat([(-gap).rename("g"), fwd_md.rename("f")], axis=1).dropna()
print(f"MenuDash ~ labour: R2 = {reg.rsquared:.4f}, slope = {reg.params['lab']:.4f}")
print(f"IC of (fair - price) gap vs next MenuDash move  = {g['g'].corr(g['f']):.4f}")
print(f"gap half-life = {(-np.log(2)/np.polyfit(gap.values[:-1], np.diff(gap.values),1)[0]):.2f} days")

# ------------------------------------------------------------------ D. Boat Party
hr("D. BOAT PARTY TICKET — seasonality + overreaction")
b = px["Boat Party Ticket"]
sm = b.rolling(21, center=True).mean()
resid = (b - sm).dropna()
print(f"variance share: smooth trend {sm.dropna().var()/b.var():.3f}, "
      f"residual {resid.var()/b.var():.3f}")
print(f"residual ACF1 = {resid.autocorr(1):.4f}, ACF2 = {resid.autocorr(2):.4f}  "
      f"(negative => overreaction that snaps back)")
fwdb = b.diff().shift(-1)
for w in (2, 3, 5, 8):
    sig = (b.rolling(w).mean() - b)
    c = pd.concat([sig.rename("s"), fwdb.rename("f")], axis=1).dropna()
    print(f"  reversion window {w:>2}: IC = {c['s'].corr(c['f']):.4f}")
seas_slope = sm.diff()
c = pd.concat([seas_slope.rename("s"), fwdb.rename("f")], axis=1).dropna()
print(f"  seasonal slope alone: IC = {c['s'].corr(c['f']):.4f}")
comb = pd.concat([((b.rolling(3).mean() - b) + 0.5 * seas_slope).rename("s"),
                  fwdb.rename("f")], axis=1).dropna()
print(f"  reversion(3) + 0.5*slope: IC = {comb['s'].corr(comb['f']):.4f}")
big = b.diff().abs() > 3 * b.diff().std()
print(f"\ndays with >3-sigma move: {int(big.sum())}")
nb = b.diff().shift(-1)
print(f"mean next-day move after a big UP move   : {nb[big & (b.diff()>0)].mean():.4f}")
print(f"mean next-day move after a big DOWN move : {nb[big & (b.diff()<0)].mean():.4f}")

# ------------------------------------------------------------------ E. Fintech
hr("E. FINTECH TOKEN — jump / flat-stretch regime")
ft = px["Fintech Token"]
rf = ft.diff().dropna()
absr = rf.abs()
q = absr.quantile([0.5, 0.75, 0.9, 0.95, 0.99])
print("abs-move quantiles:\n", q.round(3).to_string())
vol20 = rf.rolling(20).std()
print(f"\nrolling-20d vol: min {vol20.min():.3f}, max {vol20.max():.3f}, "
      f"ratio {vol20.max()/vol20.min():.1f}x  -> strong vol regimes")
print(f"ACF1 of rolling-20 vol = {vol20.autocorr(1):.4f}, ACF5 = {vol20.autocorr(5):.4f}")
hi = vol20 > vol20.median()
print(f"\nreturn ACF1 in HIGH-vol regime = {rf[hi].autocorr(1):.4f}")
print(f"return ACF1 in LOW-vol regime  = {rf[~hi].autocorr(1):.4f}")
fwd_ft = ft.diff().shift(-1)
for w in (2, 3, 5, 7, 10, 20):
    sig = ft.rolling(w).mean() - ft
    c = pd.concat([sig.rename("s"), fwd_ft.rename("f")], axis=1).dropna()
    # vol-scaled version
    cs = pd.concat([(sig / vol20).rename("s"), fwd_ft.rename("f")], axis=1).dropna()
    print(f"  window {w:>2}: raw IC = {c['s'].corr(c['f']):+.4f}   "
          f"vol-scaled IC = {cs['s'].corr(cs['f']):+.4f}")

# ------------------------------------------------------------------ F. drift vs momentum
hr("F. BREAD / SAUSAGE / JEANS — is the 'momentum' just drift?")
for ins in ["Bread", "Sausage", "Thrifted Jeans", "Sausage Sizzle"]:
    s = px[ins]
    r = s.diff()
    mu = r.mean()
    rd = r - mu                                   # drift-removed
    sd = s.iloc[0] + rd.fillna(0).cumsum()        # drift-removed price path
    fwd_raw = r.shift(-1)
    fwd_dm = rd.shift(-1)
    out = []
    for w in (5, 10, 15, 20):
        sig_raw = (s - s.rolling(w).mean())
        sig_dm = (sd - sd.rolling(w).mean())
        c1 = pd.concat([sig_raw.rename("s"), fwd_raw.rename("f")], axis=1).dropna()
        c2 = pd.concat([sig_dm.rename("s"), fwd_dm.rename("f")], axis=1).dropna()
        out.append((w, c1["s"].corr(c1["f"]), c2["s"].corr(c2["f"])))
    t = mu / (r.std() / np.sqrt(r.count()))
    print(f"\n{ins}: drift {mu:+.5f}/day (t={t:.2f}), "
          f"long-only Sharpe = {mu/r.std()*np.sqrt(252):.2f}")
    for w, a, bb in out:
        print(f"   momentum w={w:>2}: raw IC {a:+.4f}   drift-removed IC {bb:+.4f}")

# ------------------------------------------------------------------ G. Liferaft
hr("G. LIFERAFT TICKET — move structure (game-theoretic)")
lr = px["Liferaft Ticket"]
dl = lr.diff().dropna()
vc = dl.round(0).value_counts().sort_index()
print("distribution of daily moves:")
print(vc.to_string())
print(f"\nP(up) = {(dl>0).mean():.3f}, P(down) = {(dl<0).mean():.3f}, "
      f"P(flat) = {(dl==0).mean():.3f}")
sgn = np.sign(dl)
print(f"ACF1 of move sign = {pd.Series(sgn.values).autocorr(1):.4f}")
runs = (sgn != sgn.shift(1)).cumsum()
print(f"mean run length of same-direction moves = {sgn.groupby(runs).size().mean():.2f}")
print(f"price floor observed = {lr.min():.0f}, ceiling = {lr.max():.0f}")
print("NOTE: Round-1 Liferaft path reflects the Round-1 room, not a price process.")

# ------------------------------------------------------------------ H. IC stability
hr("H. IC STABILITY — first half vs second half (walk-forward sanity)")
best = {"UQ Dollar": ("rev", 17), "Fintech Token": ("rev", 5),
        "Boat Party Ticket": ("rev", 3), "MenuDash": ("rev", 9),
        "Sausage Sizzle": ("mom", 13), "Bread": ("mom", 9),
        "Sausage": ("mom", 11), "Thrifted Jeans": ("mom", 15),
        "Liferaft Ticket": ("rev", 15)}
rows = []
for ins, (kind, w) in best.items():
    s = px[ins]
    sig = (s.rolling(w).mean() - s) if kind == "rev" else (s - s.rolling(w).mean())
    f = s.diff().shift(-1)
    c = pd.concat([sig.rename("s"), f.rename("f")], axis=1).dropna()
    h = len(c) // 2
    ic1 = c.iloc[:h]["s"].corr(c.iloc[:h]["f"])
    ic2 = c.iloc[h:]["s"].corr(c.iloc[h:]["f"])
    ic = c["s"].corr(c["f"])
    t = ic * np.sqrt(len(c) - 2) / np.sqrt(max(1 - ic ** 2, 1e-12))
    rows.append({"instrument": ins, "kind": kind, "window": w, "IC_full": ic,
                 "t_stat": t, "IC_1st_half": ic1, "IC_2nd_half": ic2,
                 "stable": "YES" if ic1 * ic2 > 0 and abs(t) > 2 else "no"})
print(pd.DataFrame(rows).set_index("instrument").round(4).to_string())
pd.DataFrame(rows).to_csv(f"{OUT}/H_ic_stability.csv", index=False)

# ------------------------------------------------------------------ I. naive PnL
hr("I. GROSS PNL OF NAIVE SIGN STRATEGY (full limit, ignoring budget cap)")
rows = []
for ins, (kind, w) in best.items():
    s = px[ins]
    sig = (s.rolling(w).mean() - s) if kind == "rev" else (s - s.rolling(w).mean())
    pos = np.sign(sig).fillna(0) * LIMITS[ins]
    pnl = (pos.shift(0) * s.diff().shift(-1)).dropna()
    turn = pos.diff().abs().sum()
    rows.append({"instrument": ins, "kind": kind, "w": w,
                 "gross_pnl": pnl.sum(), "sharpe": pnl.mean() / pnl.std() * np.sqrt(252),
                 "hit_rate": (pnl > 0).mean(), "avg_notional": (pos.abs() * s).mean(),
                 "pnl_per_$budget": pnl.sum() / max((pos.abs() * s).mean(), 1),
                 "units_traded": turn})
res = pd.DataFrame(rows).set_index("instrument").sort_values("pnl_per_$budget",
                                                            ascending=False)
print(res.round(4).to_string())
print(f"\ntotal notional if all held at limit simultaneously: "
      f"${res['avg_notional'].sum():,.0f}  (budget is $600,000)")
res.to_csv(f"{OUT}/I_naive_pnl.csv")
print(f"\nCSVs -> {OUT}")
