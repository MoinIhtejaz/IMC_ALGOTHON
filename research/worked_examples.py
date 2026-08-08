"""Every arithmetic example quoted in the report, computed from the raw data so
the prose can be checked against the code."""

import os
import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.tsa.stattools import acf, adfuller

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "trader_interface", "data")
INS = ["Fintech Token", "Thrifted Jeans", "UQ Dollar", "Sausage Sizzle", "Bread",
       "MenuDash", "Sausage", "Liferaft Ticket", "Boat Party Ticket"]
px = pd.DataFrame({i: pd.read_csv(os.path.join(DATA, f"{i}_price_history.csv"))
                   .set_index("Day")["Price"] for i in INS})


def hr(t):
    print("\n" + "-" * 70); print(t); print("-" * 70)


hr("E1. UQ Dollar first 6 days, and the AR(1) arithmetic")
u = px["UQ Dollar"]
print(u.head(6).to_string())
print(f"\nday1 - day0 = {u.iloc[1]-u.iloc[0]:+.2f}, deviation on day0 = "
      f"{u.iloc[0]-100:+.2f}")
du = u.diff().dropna()
X = add_constant(u.shift(1).dropna().loc[du.index])
m = OLS(du, X).fit()
a, b = m.params.iloc[0], m.params.iloc[1]
print(f"\nOLS  dP_t = a + b*P_(t-1):  a = {a:.4f}, b = {b:.6f}, t(b) = {m.tvalues.iloc[1]:.2f}")
print(f"kappa = -b = {-b:.6f}")
print(f"mu = -a/b = {-a/b:.6f}")
print(f"half-life = ln2 / kappa = {np.log(2)/(-b):.4f} days")
print(f"residual sd = {m.resid.std():.4f}")
print(f"ADF stat/p on levels: {adfuller(u, autolag='AIC')[0]:.3f} / "
      f"{adfuller(u, autolag='AIC')[1]:.4f}")

hr("E2. ACF(1) of UQ Dollar changes, computed by hand")
r = du.values
rb = r.mean()
num = np.sum((r[1:] - rb) * (r[:-1] - rb))
den = np.sum((r - rb) ** 2)
print(f"n = {len(r)}, mean change = {rb:+.5f}")
print(f"numerator   sum (r_t - m)(r_(t-1) - m) = {num:.4f}")
print(f"denominator sum (r_t - m)^2            = {den:.4f}")
print(f"ACF(1) = {num/den:+.4f}   (statsmodels: {acf(r, nlags=1, fft=False)[1]:+.4f})")
print(f"noise band = 1.96/sqrt({len(r)}) = ±{1.96/np.sqrt(len(r)):.4f}")

hr("E3. Variance ratio VR(2) for UQ Dollar")
n = len(r)
mu = r.mean()
var1 = ((r - mu) ** 2).sum() / (n - 1)
q = 2
rq = np.array([r[i:i + q].sum() for i in range(n - q + 1)])
mdenom = q * (n - q + 1) * (1 - q / n)
varq = ((rq - q * mu) ** 2).sum() / mdenom
print(f"1-day variance          = {var1:.5f}")
print(f"2-day variance          = {varq:.5f}")
print(f"if random walk, 2-day would be 2 x 1-day = {2*var1:.5f}")
print(f"VR(2) = varq/var1 = {varq/var1:.4f}")
for qq in (5, 10, 20):
    rqq = np.array([r[i:i + qq].sum() for i in range(n - qq + 1)])
    md = qq * (n - qq + 1) * (1 - qq / n)
    vq = ((rqq - qq * mu) ** 2).sum() / md
    print(f"VR({qq:>2}) = {vq/var1:.4f}")

hr("E4. Hurst exponent for UQ Dollar and Thrifted Jeans")
for ins in ["UQ Dollar", "Thrifted Jeans", "Sausage Sizzle"]:
    ts = px[ins].values.astype(float)
    lags = range(2, 40)
    tau = [np.std(ts[l:] - ts[:-l]) for l in lags]
    H = np.polyfit(np.log(list(lags)), np.log(tau), 1)[0]
    print(f"{ins:>16}: sd of 2-day gaps = {tau[0]:.4f}, "
          f"sd of 20-day gaps = {tau[18]:.4f}, ratio = {tau[18]/tau[0]:.2f}, H = {H:.4f}")
    print(f"{'':>16}  a random walk would give ratio sqrt(20/2) = {np.sqrt(10):.2f}")

hr("E5. IC -> t-statistic conversion")
for ic, nn in [(0.9601, 353), (0.6975, 348), (0.2801, 284), (0.1327, 363),
               (0.0971, 350)]:
    t = ic * np.sqrt(nn - 2) / np.sqrt(1 - ic ** 2)
    print(f"IC = {ic:.4f}, n = {nn:>3}  ->  t = {t:8.2f}")

hr("E6. Sausage Sizzle recipe — a single concrete day")
d = pd.DataFrame({"sz": px["Sausage Sizzle"], "br1": px["Bread"].shift(1),
                  "sa1": px["Sausage"].shift(1)}).dropna()
reg = OLS(d["sz"], add_constant(d[["br1", "sa1"]])).fit()
A, B, C = reg.params["br1"], reg.params["sa1"], reg.params["const"]
print(f"fitted: sizzle_t = {C:.4f} + {A:.5f}*bread_(t-1) + {B:.5f}*sausage_(t-1)")
print(f"R2 = {reg.rsquared:.4f}, residual sd = {reg.resid.std():.4f}")
t0 = 200
print(f"\nday {t0-1}: bread = {px['Bread'].iloc[t0-1]:.2f}, "
      f"sausage = {px['Sausage'].iloc[t0-1]:.2f}")
print(f"predicted sizzle day {t0} = {C:.4f} + {A:.5f}*{px['Bread'].iloc[t0-1]:.2f}"
      f" + {B:.5f}*{px['Sausage'].iloc[t0-1]:.2f} = "
      f"{C + A*px['Bread'].iloc[t0-1] + B*px['Sausage'].iloc[t0-1]:.4f}")
print(f"actual sizzle day {t0}    = {px['Sausage Sizzle'].iloc[t0]:.4f}")
lab = d["sz"] - A * d["br1"] - B * d["sa1"]
print(f"\nlabour residual: mean {lab.mean():.4f}, sd {lab.std():.4f}, "
      f"sd of daily CHANGE {lab.diff().std():.4f}")
known = A * px["Bread"].diff() + B * px["Sausage"].diff()
fwd = px["Sausage Sizzle"].diff().shift(-1)
cc = pd.concat([known.rename("k"), fwd.rename("f")], axis=1).dropna()
print(f"IC(known move, tomorrow's sizzle move) = {cc['k'].corr(cc['f']):.4f}, "
      f"R2 = {cc['k'].corr(cc['f'])**2:.4f}")
print(f"\nexample: on day {t0}, bread moved "
      f"{px['Bread'].iloc[t0]-px['Bread'].iloc[t0-1]:+.2f} and sausage "
      f"{px['Sausage'].iloc[t0]-px['Sausage'].iloc[t0-1]:+.2f}")
print(f"  => predicted sizzle move for day {t0+1} = "
      f"{A*(px['Bread'].iloc[t0]-px['Bread'].iloc[t0-1]) + B*(px['Sausage'].iloc[t0]-px['Sausage'].iloc[t0-1]):+.4f}")
print(f"  => actual sizzle move day {t0+1}       = "
      f"{px['Sausage Sizzle'].iloc[t0+1]-px['Sausage Sizzle'].iloc[t0]:+.4f}")

hr("E7. Fintech Token volatility regimes")
ft = px["Fintech Token"]
rf = ft.diff().dropna()
v = rf.rolling(20).std()
print(f"quietest 20-day window: sd = {v.min():.3f} around day {int(v.idxmin())}")
print(f"wildest  20-day window: sd = {v.max():.3f} around day {int(v.idxmax())}")
print(f"ratio = {v.max()/v.min():.2f}x")
print(f"ACF(1) of that vol series = {v.autocorr(1):.4f}")
a = acf(rf.abs(), nlags=10, fft=False)
print(f"|move| ACF: lag1 {a[1]:.4f}, lag5 {a[5]:.4f}, lag10 {a[10]:.4f}")
print(f"\nGARCH persistence 0.9855 -> vol half-life = "
      f"{np.log(0.5)/np.log(0.9855):.1f} days")

hr("E8. Liferaft expected value")
lrs = px["Liferaft Ticket"].diff().dropna()
nd = int((lrs < 0).sum()); nu = int((lrs > 0).sum())
print(f"down days (-5000): {nd}, up days (+8000): {nu}, total {nd+nu}")
p_long_majority = nd / (nd + nu)
print(f"observed P(majority long) = {nd}/{nd+nu} = {p_long_majority:.4f}")
print(f"breakeven P = 8000/(8000+5000) = {8000/13000:.4f}")
print(f"EV(long)  = 8000*(1-p) - 5000*p = "
      f"{8000*(1-p_long_majority) - 5000*p_long_majority:+.1f}")
print(f"EV(short) = 5000*p - 8000*(1-p) = "
      f"{5000*p_long_majority - 8000*(1-p_long_majority):+.1f}")

hr("E9. Sample-size reality check")
for nn in (365, 100, 50):
    print(f"n = {nn:>3}: an IC of {1.96/np.sqrt(nn):.3f} is the 5% threshold; "
          f"anything smaller is indistinguishable from luck")
print(f"\nwith n=365 and true IC=0.13, the 95% CI on the estimate is roughly "
      f"±{1.96/np.sqrt(365):.3f} -> [{0.13-1.96/np.sqrt(365):.3f}, "
      f"{0.13+1.96/np.sqrt(365):.3f}]")
