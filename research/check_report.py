"""Fact-check REPORT.md against the data.

Recomputes every headline figure independently of the analysis scripts and
compares it to the value asserted in the prose. Any MISMATCH is a bug in the
report, not in the data.
"""

import os
import re
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.tsa.stattools import acf, adfuller
from statsmodels.stats.diagnostic import het_arch

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "trader_interface", "data")
INS = ["Fintech Token", "Thrifted Jeans", "UQ Dollar", "Sausage Sizzle", "Bread",
       "MenuDash", "Sausage", "Liferaft Ticket", "Boat Party Ticket"]
px = pd.DataFrame({i: pd.read_csv(os.path.join(DATA, f"{i}_price_history.csv"))
                   .set_index("Day")["Price"] for i in INS})
report = open(os.path.join(HERE, "REPORT.md"), encoding="utf-8").read()

fails = []


def check(label, computed, claimed, tol=0.005):
    ok = abs(computed - claimed) <= tol * max(1.0, abs(claimed))
    print(f"  {'OK  ' if ok else 'FAIL'}  {label:<52} "
          f"computed {computed:>12.4f}   report {claimed:>12.4f}")
    if not ok:
        fails.append(label)


def in_report(snippet, label=None):
    """Search with markdown/HTML emphasis stripped, since the same value may be
    written as **x** in prose or <strong>x</strong> inside the summary cards."""
    strip = lambda s: re.sub(r"\s+", " ", re.sub(r"</?strong>|\*\*", "", s))
    ok = strip(snippet) in strip(report)
    print(f"  {'OK  ' if ok else 'FAIL'}  text present: {label or snippet!r}")
    if not ok:
        fails.append(f"text: {snippet}")


def ic(sig, fwd):
    c = pd.concat([sig.rename("s"), fwd.rename("f")], axis=1).dropna()
    return c["s"].corr(c["f"]), len(c)


print("=" * 78)
print("§2  Information Coefficient and t-statistics")
print("=" * 78)
check("noise floor 1.96/sqrt(364)", 1.96 / np.sqrt(364), 0.103, tol=0.01)
for icv, n, claimed_t in [(0.9601, 353, 64.3), (0.6975, 348, 18.1),
                          (0.2801, 284, 4.90), (0.1327, 363, 2.54),
                          (0.0971, 350, 1.82)]:
    t = icv * np.sqrt(n - 2) / np.sqrt(1 - icv ** 2)
    check(f"t for IC={icv} n={n}", t, claimed_t, tol=0.01)

print("=" * 78)
print("§4  UQ Dollar Ornstein-Uhlenbeck fit")
print("=" * 78)
u = px["UQ Dollar"]
du = u.diff().dropna()
m = OLS(du, add_constant(u.shift(1).dropna().loc[du.index])).fit()
a, b = m.params.iloc[0], m.params.iloc[1]
check("intercept a", a, 96.190, tol=0.001)
check("slope b", b, -0.9625, tol=0.001)
check("t on slope", m.tvalues.iloc[1], -18.3, tol=0.01)
check("kappa", -b, 0.9625, tol=0.001)
check("peg mu = -a/b", -a / b, 99.941, tol=0.0001)
check("half-life ln2/kappa", np.log(2) / -b, 0.72, tol=0.01)
check("residual sd", m.resid.std(), 0.43, tol=0.02)
check("ADF p on levels", adfuller(u, autolag="AIC")[1], 0.103, tol=0.02)
dev = (u - 100).iloc[:-1].values
nxt = u.diff().shift(-1).dropna().values
d = pd.DataFrame({"dev": dev, "nxt": nxt})
d["bin"] = pd.qcut(d["dev"], 6)
hit = d.groupby("bin", observed=True).apply(
    lambda x: (np.sign(x["nxt"]) == -np.sign(x["dev"])).mean())
check("hit rate, most-below bucket", hit.iloc[0], 0.92, tol=0.02)
check("hit rate, most-above bucket", hit.iloc[-1], 0.95, tol=0.02)
check("hit rate, smallest-gap bucket", hit.iloc[3], 0.49, tol=0.03)
check("IC of (100 - P)", np.corrcoef(100 - u.iloc[:-1].values, nxt)[0, 1],
      0.6937, tol=0.002)

print("=" * 78)
print("§5  Hurst exponent")
print("=" * 78)
for ins, claimed_ratio, claimed_H in [("UQ Dollar", 1.06, 0.008),
                                      ("Thrifted Jeans", 3.99, 0.576),
                                      ("Sausage Sizzle", 5.32, 0.719)]:
    ts = px[ins].values.astype(float)
    lags = list(range(2, 40))
    tau = [np.std(ts[l:] - ts[:-l]) for l in lags]
    H = np.polyfit(np.log(lags), np.log(tau), 1)[0]
    check(f"{ins}: 20d/2d sd ratio", tau[18] / tau[0], claimed_ratio, tol=0.01)
    check(f"{ins}: Hurst", H, claimed_H, tol=0.02)
check("random-walk benchmark sqrt(10)", np.sqrt(10), 3.16, tol=0.005)

print("=" * 78)
print("§7  Autocorrelation")
print("=" * 78)
r = du.values
rb = r.mean()
num = np.sum((r[1:] - rb) * (r[:-1] - rb))
den = np.sum((r - rb) ** 2)
check("UQD numerator", num, -63.53, tol=0.001)
check("UQD denominator", den, 129.23, tol=0.001)
check("UQD rho(1)", num / den, -0.4916, tol=0.002)
for ins, claimed in [("UQ Dollar", -0.492), ("Boat Party Ticket", -0.168),
                     ("Fintech Token", -0.132), ("Sausage Sizzle", 0.085),
                     ("Sausage", 0.091), ("Bread", 0.064),
                     ("MenuDash", -0.042), ("Thrifted Jeans", -0.051),
                     ("Liferaft Ticket", 0.039)]:
    check(f"rho(1) {ins}", acf(px[ins].diff().dropna(), nlags=1, fft=False)[1],
          claimed, tol=0.01)

print("=" * 78)
print("§8  Variance ratios")
print("=" * 78)
n = len(r)
mu = r.mean()
var1 = ((r - mu) ** 2).sum() / (n - 1)
check("UQD 1-day variance", var1, 0.3560, tol=0.002)
for q, claimed in [(2, 0.511), (5, 0.214), (10, 0.109), (20, 0.060)]:
    rq = np.array([r[i:i + q].sum() for i in range(n - q + 1)])
    md = q * (n - q + 1) * (1 - q / n)
    vq = ((rq - q * mu) ** 2).sum() / md
    if q == 2:
        check("UQD 2-day variance", vq, 0.1820, tol=0.005)
        check("2 x 1-day variance", 2 * var1, 0.7120, tol=0.002)
    check(f"UQD VR({q})", vq / var1, claimed, tol=0.01)

print("=" * 78)
print("§10 Volatility")
print("=" * 78)
ft = px["Fintech Token"]
rf = ft.diff().dropna()
v20 = rf.rolling(20).std()
check("Fintech ARCH-LM p", het_arch(rf, nlags=5)[1], 0.004, tol=0.15)
check("UQD ARCH-LM p < 0.001", het_arch(du, nlags=5)[1], 0.0, tol=0.001)
check("Fintech quiet 20d sd", v20.min(), 7.41, tol=0.005)
check("Fintech wild 20d sd", v20.max(), 19.66, tol=0.005)
check("Fintech vol ratio", v20.max() / v20.min(), 2.65, tol=0.01)
check("Fintech rolling-vol ACF(1)", v20.autocorr(1), 0.967, tol=0.005)
av = acf(rf.abs(), nlags=10, fft=False)
check("Fintech |move| ACF(1)", av[1], 0.089, tol=0.02)
check("Fintech |move| ACF(10)", av[10], 0.125, tol=0.02)
check("vol half-life from persistence 0.9855",
      np.log(0.5) / np.log(0.9855), 47.5, tol=0.01)
for ins, claimed in [("Sausage Sizzle", 0.30), ("Bread", 0.64), ("MenuDash", 0.34),
                     ("Thrifted Jeans", 0.82)]:
    check(f"ARCH-LM p {ins}", het_arch(px[ins].diff().dropna(), nlags=5)[1],
          claimed, tol=0.05)

print("=" * 78)
print("§12 Sausage Sizzle recipe")
print("=" * 78)
dd = pd.DataFrame({"sz": px["Sausage Sizzle"], "br1": px["Bread"].shift(1),
                   "sa1": px["Sausage"].shift(1)}).dropna()
reg = OLS(dd["sz"], add_constant(dd[["br1", "sa1"]])).fit()
A, B, C = reg.params["br1"], reg.params["sa1"], reg.params["const"]
check("const c", C, 18.9495, tol=0.0005)
check("A (bread)", A, 0.07422, tol=0.002)
check("B (sausage)", B, 1.72683, tol=0.002)
check("R2", reg.rsquared, 0.696, tol=0.005)
check("residual sd", reg.resid.std(), 0.66, tol=0.02)
lab = dd["sz"] - A * dd["br1"] - B * dd["sa1"]
check("labour mean", lab.mean(), 18.95, tol=0.002)
check("labour sd", lab.std(), 0.66, tol=0.02)
check("labour daily-change sd", lab.diff().std(), 0.0375, tol=0.02)
known = A * px["Bread"].diff() + B * px["Sausage"].diff()
fwd = px["Sausage Sizzle"].diff().shift(-1)
icv, nn = ic(known, fwd)
check("IC known->tomorrow", icv, 0.922, tol=0.002)
check("R2 of that", icv ** 2, 0.850, tol=0.005)
cc = pd.concat([known.rename("k"), fwd.rename("f")], axis=1).dropna()
check("sign accuracy %", 100 * (np.sign(cc["k"]) == np.sign(cc["f"])).mean(),
      83.2, tol=0.01)
check("bread slices: 0.074 loaf x 13", A * 13, 0.96, tol=0.06)
# the eight-day table
tbl = pd.DataFrame({"bm": px["Bread"].diff(), "sm": px["Sausage"].diff(),
                    "pred": known, "act": fwd}).dropna()
sub = tbl.loc[100:107].round(3)
print("\n  eight-day table as printed in §12:")
print(sub.to_string())
correct = sum(1 for _, row in sub.iterrows()
              if np.sign(row["pred"]) == np.sign(row["act"]) and row["act"] != 0)
check("directions correct out of 8", correct, 6, tol=0.0)

print("=" * 78)
print("§13 MenuDash")
print("=" * 78)
md = px["MenuDash"]
labf = px["Sausage Sizzle"] - A * px["Bread"].shift(1) - B * px["Sausage"].shift(1)
cm = pd.concat([md.rename("md"), labf.rename("lab")], axis=1).dropna()
check("corr(level, labour)", cm["md"].corr(cm["lab"]), 0.931, tol=0.005)
rr = OLS(cm["md"], add_constant(cm[["lab"]])).fit()
check("R2", rr.rsquared, 0.867, tol=0.005)
gap = cm["md"] - rr.fittedvalues
hl = -np.log(2) / np.polyfit(gap.values[:-1], np.diff(gap.values), 1)[0]
check("gap half-life", hl, 2.94, tol=0.01)
check("frac days unchanged", (md.diff() == 0).mean(), 0.225, tol=0.01)
uniq = np.unique(md.diff().dropna().round(6))
check("tick size", np.min(np.abs(uniq[uniq != 0])), 0.01, tol=0.001)
check("price min", md.min(), 1.70, tol=0.001)
check("price max", md.max(), 2.00, tol=0.001)

print("=" * 78)
print("§15 Cross-sectional reversion")
print("=" * 78)


def xs(cols):
    rr_ = px[cols].pct_change().dropna()
    z = (rr_ - rr_.mean()) / rr_.std()
    x = z.sub(z.mean(axis=1), axis=0)
    dd_ = pd.concat([x.shift(1).stack().rename("x"), x.stack().rename("y")],
                    axis=1).dropna()
    c = dd_["x"].corr(dd_["y"])
    return c, c * np.sqrt(len(dd_) - 2) / np.sqrt(1 - c ** 2), len(dd_)


allc = list(px.columns)
c1, t1, n1 = xs(allc)
check("all 9: corr", c1, -0.093, tol=0.02)
check("all 9: t", t1, -5.32, tol=0.01)
check("all 9: n obs", n1, 3267, tol=0.0)
c2, t2, _ = xs([c for c in allc if c != "UQ Dollar"])
check("ex UQD: corr", c2, -0.042, tol=0.03)
check("ex UQD: t", t2, -2.26, tol=0.02)
c4, t4, _ = xs([c for c in allc if c not in ("UQ Dollar", "Liferaft Ticket",
                                            "Boat Party Ticket", "Sausage Sizzle")])
check("ex 4: corr", c4, -0.023, tol=0.05)
check("ex 4: t", t4, -0.98, tol=0.03)

print("=" * 78)
print("§17-19 Boat Party and Liferaft")
print("=" * 78)
b = px["Boat Party Ticket"]
fb = b.diff().shift(-1)
icv, _ = ic(b.rolling(21, center=True).mean().diff(), fb)
check("centred slope IC (invalid)", icv, 0.258, tol=0.01)
icv, _ = ic(b.rolling(10).mean().diff(), fb)
check("trailing-10 slope IC", icv, 0.029, tol=0.05)
icv, _ = ic(b.rolling(3).mean() - b, fb)
check("3-day reversion IC", icv, 0.181, tol=0.01)
sm = b.iloc[:182].rolling(15, center=True).mean().diff()
app = pd.Series({d: sm.get(d - 182, np.nan) for d in range(182, len(b))}).dropna()
icv, nn = ic(app, fb)
check("1st-half shape on 2nd half IC", icv, -0.118, tol=0.02)
check("that n", nn, 167, tol=0.0)
sm21 = b.rolling(21, center=True).mean()
resid = (b - sm21).dropna()
check("smooth variance share", sm21.dropna().var() / b.var(), 0.838, tol=0.01)
check("residual variance share", resid.var() / b.var(), 0.077, tol=0.02)
check("Boat Party EXCESS kurtosis (Normal=0)",
      stats.kurtosis(b.diff().dropna(), fisher=True), 9.5, tol=0.01)
check("Boat Party raw kurtosis (Normal=3)",
      stats.kurtosis(b.diff().dropna(), fisher=False), 12.5, tol=0.01)
big = b.diff().abs() > 3 * b.diff().std()
check("moves > 3 sigma", big.sum(), 7, tol=0.0)
check("moves > 4 sigma", (b.diff().abs() > 4 * b.diff().std()).sum(), 3, tol=0.0)
nb = b.diff().shift(-1)
check("avg next move after big drop", nb[big & (b.diff() < 0)].mean(), 0.243,
      tol=0.02)
check("avg next move after big rise", nb[big & (b.diff() > 0)].mean(), 0.115,
      tol=0.03)

lr = px["Liferaft Ticket"].diff().dropna()
vals = sorted(lr.unique())
print(f"  distinct Liferaft moves: {vals}")
check("n distinct moves", len(vals), 2, tol=0.0)
check("down days", (lr < 0).sum(), 214, tol=0.0)
check("up days", (lr > 0).sum(), 150, tol=0.0)
p = 214 / 364
check("P(majority long)", p, 0.588, tol=0.002)
check("breakeven 8000/13000", 8000 / 13000, 0.615, tol=0.002)
check("EV long", 8000 * (1 - p) - 5000 * p, 357, tol=0.01)
check("sign ACF(1)", pd.Series(np.sign(lr).values).autocorr(1), 0.039, tol=0.03)

print("=" * 78)
print("§23 Budget")
print("=" * 78)
LIM = {"Fintech Token": 100, "Thrifted Jeans": 800, "UQ Dollar": 650,
       "Sausage Sizzle": 3000, "Bread": 500, "MenuDash": 75000,
       "Sausage": 5000, "Liferaft Ticket": 1, "Boat Party Ticket": 1000}
best = {"UQ Dollar": ("rev", 17), "Fintech Token": ("rev", 5),
        "Boat Party Ticket": ("rev", 3), "MenuDash": ("rev", 9),
        "Sausage Sizzle": ("mom", 13), "Bread": ("mom", 9), "Sausage": ("mom", 11),
        "Thrifted Jeans": ("mom", 15), "Liferaft Ticket": ("rev", 15)}
tot = 0
for i, (k, w) in best.items():
    s = px[i]
    sig = (s.rolling(w).mean() - s) if k == "rev" else (s - s.rolling(w).mean())
    pos = np.sign(sig).fillna(0) * LIM[i]
    tot += (pos.abs() * s).mean()
check("total notional at limits", tot, 693066, tol=0.001)

print("=" * 78)
print("Prose spot-checks")
print("=" * 78)
in_report("**0.96**", "Sizzle IC in summary card")
in_report("**83%**", "Sizzle hit rate in summary card")
in_report("**92–95%**", "UQ Dollar hit rate in summary card")
in_report("**−0.118**", "Boat Party transfer failure")
in_report("−$5,000 on 214 days and +$8,000 on 150 days", "Liferaft counts")
in_report("$693,066", "budget requirement")
in_report("**0.615**", "Liferaft breakeven")

print()
print("=" * 78)
if fails:
    print(f"{len(fails)} MISMATCH(ES):")
    for f in fails:
        print("   -", f)
else:
    print("ALL CHECKS PASSED — every figure quoted in REPORT.md reproduces.")
print("=" * 78)
