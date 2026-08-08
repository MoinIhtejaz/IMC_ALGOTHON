"""
AlgoJam 3 — structural diagnostics on Round 1 price histories.

Runs, per instrument and cross-sectionally:
  1. Structure      — stationarity (ADF/KPSS), Hurst, drift, return distribution
  2. Autocorrelation — ACF/PACF, Ljung-Box, variance ratio, optimal reversion window
  3. Volatility      — ARCH-LM, |return| ACF, GARCH(1,1) persistence
  4. Cross-section   — contemporaneous & lagged correlation, Granger, cointegration
  5. Cross-sectional mean reversion — rank-reversal / winner-loser test
  6. Seasonality     — FFT periodogram, jump detection

Usage:  python structure_tests.py
Writes: research/out/*.csv, research/out/*.png, research/out/report.md
"""

import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats, signal
from statsmodels.tsa.stattools import adfuller, kpss, acf, pacf, grangercausalitytests, coint
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from arch import arch_model

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "trader_interface", "data")
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

INSTRUMENTS = [
    "Fintech Token", "Thrifted Jeans", "UQ Dollar", "Sausage Sizzle",
    "Bread", "MenuDash", "Sausage", "Liferaft Ticket", "Boat Party Ticket",
]

LIMITS = {
    "Fintech Token": 100, "Thrifted Jeans": 800, "UQ Dollar": 650,
    "Sausage Sizzle": 3000, "Bread": 500, "MenuDash": 75000,
    "Sausage": 5000, "Liferaft Ticket": 1, "Boat Party Ticket": 1000,
}


def load():
    frames = {}
    for ins in INSTRUMENTS:
        p = os.path.join(DATA, f"{ins}_price_history.csv")
        df = pd.read_csv(p)
        frames[ins] = df.set_index("Day")["Price"]
    return pd.DataFrame(frames)


# ---------------------------------------------------------------- helpers

def hurst(ts, max_lag=40):
    """Rescaled-range style Hurst via variance of lagged differences."""
    ts = np.asarray(ts, dtype=float)
    lags = range(2, max_lag)
    tau = []
    for lag in lags:
        d = ts[lag:] - ts[:-lag]
        s = np.std(d)
        tau.append(s if s > 0 else 1e-12)
    poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
    return poly[0]


def variance_ratio(r, q):
    """Lo-MacKinlay VR(q) with heteroskedasticity-robust z-stat.
    VR < 1 => mean reversion, VR > 1 => trending."""
    r = np.asarray(r, dtype=float)
    n = len(r)
    mu = r.mean()
    var1 = ((r - mu) ** 2).sum() / (n - 1)
    rq = np.array([r[i:i + q].sum() for i in range(n - q + 1)])
    m = q * (n - q + 1) * (1 - q / n)
    varq = ((rq - q * mu) ** 2).sum() / m
    vr = varq / var1
    # robust variance
    theta = 0.0
    for j in range(1, q):
        num = (((r[j:] - mu) ** 2) * ((r[:-j] - mu) ** 2)).sum()
        den = (((r - mu) ** 2).sum()) ** 2
        delta = n * num / den
        theta += ((2 * (q - j) / q) ** 2) * delta
    z = (vr - 1) / np.sqrt(theta) if theta > 0 else np.nan
    return vr, z


def half_life(series):
    """OU half-life from AR(1) on levels: dP_t = a + b*P_{t-1}."""
    y = np.asarray(series, dtype=float)
    dy = np.diff(y)
    x = y[:-1]
    b, a = np.polyfit(x, dy, 1)
    if b >= 0:
        return np.nan
    return -np.log(2) / b


# ---------------------------------------------------------------- 1. structure

def structure_tests(px):
    rows = []
    for ins in px.columns:
        s = px[ins].dropna()
        r = s.diff().dropna()                     # arithmetic returns
        lr = np.log(s).diff().dropna() if (s > 0).all() else r / s.shift(1).dropna()

        try:
            adf_p = adfuller(s, autolag="AIC")[1]
        except Exception:
            adf_p = np.nan
        try:
            kpss_p = kpss(s, regression="c", nlags="auto")[1]
        except Exception:
            kpss_p = np.nan
        try:
            adf_r_p = adfuller(r, autolag="AIC")[1]
        except Exception:
            adf_r_p = np.nan

        drift = r.mean()
        drift_t = drift / (r.std() / np.sqrt(len(r))) if r.std() > 0 else np.nan

        rows.append({
            "instrument": ins,
            "n": len(s),
            "price_start": s.iloc[0], "price_end": s.iloc[-1],
            "price_mean": s.mean(), "price_std": s.std(),
            "total_ret_%": 100 * (s.iloc[-1] / s.iloc[0] - 1),
            "daily_vol_$": r.std(),
            "daily_vol_%": 100 * lr.std(),
            "ann_vol_%": 100 * lr.std() * np.sqrt(252),
            "drift_$/day": drift,
            "drift_t": drift_t,
            "skew": stats.skew(r), "kurt": stats.kurtosis(r),
            "jb_p": stats.jarque_bera(r)[1],
            "adf_p_level": adf_p,
            "kpss_p_level": kpss_p,
            "adf_p_ret": adf_r_p,
            "hurst": hurst(s.values),
            "half_life_d": half_life(s.values),
            "pct_zero_moves": 100 * (r == 0).mean(),
            "max_dd_%": 100 * ((s / s.cummax()) - 1).min(),
            "notional_at_limit": LIMITS[ins] * s.mean(),
        })
    return pd.DataFrame(rows).set_index("instrument")


# ---------------------------------------------------------------- 2. autocorr

def autocorr_tests(px, max_lag=15):
    acf_rows, summary = [], []
    for ins in px.columns:
        r = px[ins].diff().dropna()
        a = acf(r, nlags=max_lag, fft=False)
        p = pacf(r, nlags=max_lag)
        se = 1.96 / np.sqrt(len(r))
        acf_rows.append(pd.Series(a[1:], index=[f"lag{i}" for i in range(1, max_lag + 1)], name=ins))

        lb = acorr_ljungbox(r, lags=[1, 5, 10, 20], return_df=True)
        vr_res = {q: variance_ratio(r.values, q) for q in (2, 5, 10, 20)}

        # best mean-reversion window: corr(mean(p[-w:]) - p[-1], next return)
        best_w, best_ic = None, 0.0
        s = px[ins].values
        for w in range(2, 41):
            sig, fwd = [], []
            for t in range(w, len(s) - 1):
                sig.append(s[t - w:t].mean() - s[t])
                fwd.append(s[t + 1] - s[t])
            if np.std(sig) > 1e-12:
                ic = np.corrcoef(sig, fwd)[0, 1]
                if abs(ic) > abs(best_ic):
                    best_ic, best_w = ic, w

        # momentum window: corr(p[-1] - mean(p[-w:]), next return) is just -above
        summary.append({
            "instrument": ins,
            "acf1": a[1], "acf2": a[2], "acf3": a[3], "acf5": a[5], "acf10": a[10],
            "acf_signif_band": se,
            "pacf1": p[1], "pacf2": p[2],
            "LB_p_lag1": lb["lb_pvalue"].iloc[0],
            "LB_p_lag5": lb["lb_pvalue"].iloc[1],
            "LB_p_lag10": lb["lb_pvalue"].iloc[2],
            "LB_p_lag20": lb["lb_pvalue"].iloc[3],
            "VR2": vr_res[2][0], "VR2_z": vr_res[2][1],
            "VR5": vr_res[5][0], "VR5_z": vr_res[5][1],
            "VR10": vr_res[10][0], "VR10_z": vr_res[10][1],
            "VR20": vr_res[20][0], "VR20_z": vr_res[20][1],
            "best_window": best_w,
            "best_IC": best_ic,
            "signal_type": "REVERSION" if best_ic > 0 else "MOMENTUM",
        })
    return pd.DataFrame(acf_rows), pd.DataFrame(summary).set_index("instrument")


# ---------------------------------------------------------------- 3. vol

def vol_tests(px):
    rows = []
    for ins in px.columns:
        r = px[ins].diff().dropna()
        absr = r.abs()
        a_abs = acf(absr, nlags=10, fft=False)
        a_sq = acf(r ** 2, nlags=10, fft=False)

        try:
            arch_lm = het_arch(r, nlags=5)
            arch_p = arch_lm[1]
        except Exception:
            arch_p = np.nan

        alpha = beta = pers = np.nan
        try:
            scale = 100.0 / max(r.std(), 1e-9)
            am = arch_model(r * scale, vol="Garch", p=1, q=1, mean="Zero", rescale=False)
            res = am.fit(disp="off", show_warning=False)
            alpha = res.params.get("alpha[1]", np.nan)
            beta = res.params.get("beta[1]", np.nan)
            pers = alpha + beta
        except Exception:
            pass

        # realised-vol autocorrelation over 10d windows
        rv = absr.rolling(10).mean().dropna()
        rv_ac1 = rv.autocorr(1) if len(rv) > 5 else np.nan

        rows.append({
            "instrument": ins,
            "absret_acf1": a_abs[1], "absret_acf5": a_abs[5], "absret_acf10": a_abs[10],
            "sqret_acf1": a_sq[1], "sqret_acf5": a_sq[5],
            "ARCH_LM_p": arch_p,
            "GARCH_alpha": alpha, "GARCH_beta": beta, "GARCH_persistence": pers,
            "vol_halflife_d": (np.log(0.5) / np.log(pers)) if (pers and pers < 1) else np.nan,
            "RV10_acf1": rv_ac1,
            "vol_clustering": "YES" if (arch_p == arch_p and arch_p < 0.05) else "no",
        })
    return pd.DataFrame(rows).set_index("instrument")


# ---------------------------------------------------------------- 4. cross-section

def cross_tests(px, max_lead=5):
    r = px.diff().dropna()
    contemp = r.corr()

    # lagged: corr(X_t-k, Y_t) for each k
    lead_lag = []
    for x in px.columns:
        for y in px.columns:
            if x == y:
                continue
            for k in range(1, max_lead + 1):
                c = r[x].shift(k).corr(r[y])
                lead_lag.append({"leader": x, "follower": y, "lag": k, "corr": c,
                                 "abs": abs(c)})
    ll = pd.DataFrame(lead_lag).sort_values("abs", ascending=False)

    # Granger causality on returns (leader -> follower), lag 1..3
    gr = []
    for x in px.columns:
        for y in px.columns:
            if x == y:
                continue
            try:
                d = pd.concat([r[y], r[x]], axis=1).dropna()
                res = grangercausalitytests(d, maxlag=3, verbose=False)
                pmin = min(res[l][0]["ssr_ftest"][1] for l in (1, 2, 3))
                gr.append({"leader": x, "follower": y, "granger_p_min": pmin})
            except Exception:
                pass
    gdf = pd.DataFrame(gr).sort_values("granger_p_min")

    # cointegration on levels
    co = []
    cols = list(px.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            try:
                t, p, _ = coint(px[cols[i]], px[cols[j]])
                # hedge ratio + spread half-life
                b = np.polyfit(px[cols[j]], px[cols[i]], 1)[0]
                spread = px[cols[i]] - b * px[cols[j]]
                co.append({"a": cols[i], "b": cols[j], "coint_p": p,
                           "hedge_ratio": b, "spread_halflife": half_life(spread.values)})
            except Exception:
                pass
    cdf = pd.DataFrame(co).sort_values("coint_p")

    return contemp, ll, gdf, cdf


def cross_sectional_reversion(px):
    """Do yesterday's cross-sectional winners become tomorrow's losers?
    Standardise each instrument's return, then regress next-day z-return on
    today's demeaned z-return across the panel."""
    r = px.pct_change().dropna()
    z = (r - r.mean()) / r.std()               # per-instrument standardisation
    xs = z.sub(z.mean(axis=1), axis=0)         # demean across instruments each day

    rows = []
    for lag in range(1, 6):
        x = xs.shift(lag).stack()
        y = xs.stack()
        d = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
        c = d["x"].corr(d["y"])
        t = c * np.sqrt(len(d) - 2) / np.sqrt(max(1 - c ** 2, 1e-12))
        rows.append({"lag": lag, "xs_autocorr": c, "t_stat": t, "n": len(d),
                     "effect": "XS MEAN REVERSION" if c < 0 else "XS MOMENTUM"})
    panel = pd.DataFrame(rows)

    # per-instrument beta to the cross-sectional loser/winner factor
    per = []
    for ins in px.columns:
        d = pd.concat([xs[ins].shift(1).rename("x"), xs[ins].rename("y")], axis=1).dropna()
        c = d["x"].corr(d["y"])
        per.append({"instrument": ins, "xs_demeaned_acf1": c})
    return panel, pd.DataFrame(per).set_index("instrument")


# ---------------------------------------------------------------- 5. seasonality

def seasonality_tests(px):
    rows = []
    for ins in px.columns:
        s = px[ins].dropna().values
        x = s - s.mean()
        f, Pxx = signal.periodogram(x, fs=1.0)
        f, Pxx = f[1:], Pxx[1:]
        order = np.argsort(Pxx)[::-1][:3]
        periods = [round(1 / f[i], 1) for i in order]
        power_share = [round(float(Pxx[i] / Pxx.sum()), 3) for i in order]

        r = np.diff(s)
        thresh = 4 * np.std(r)
        jumps = int((np.abs(r) > thresh).sum())

        # weekly (5d) and calendar (7d) seasonality F-test on returns
        def anova_p(period):
            groups = [r[i::period] for i in range(period)]
            groups = [g for g in groups if len(g) > 2]
            try:
                return stats.f_oneway(*groups)[1]
            except Exception:
                return np.nan

        rows.append({
            "instrument": ins,
            "top_period_1": periods[0], "power_1": power_share[0],
            "top_period_2": periods[1], "power_2": power_share[1],
            "top_period_3": periods[2], "power_3": power_share[2],
            "n_jumps_4sig": jumps,
            "jump_frac_%": 100 * jumps / len(r),
            "anova_p_period5": anova_p(5),
            "anova_p_period7": anova_p(7),
            "anova_p_period30": anova_p(30),
        })
    return pd.DataFrame(rows).set_index("instrument")


# ---------------------------------------------------------------- main

def main():
    px = load()
    print(f"Loaded {px.shape[0]} days x {px.shape[1]} instruments\n")

    print("=" * 78); print("1. STRUCTURE"); print("=" * 78)
    st = structure_tests(px)
    print(st[["price_start", "price_end", "total_ret_%", "daily_vol_%", "ann_vol_%",
              "drift_t", "adf_p_level", "kpss_p_level", "hurst", "half_life_d",
              "pct_zero_moves"]].round(4).to_string())
    st.to_csv(f"{OUT}/1_structure.csv")

    print("\n" + "=" * 78); print("1b. DISTRIBUTION"); print("=" * 78)
    print(st[["skew", "kurt", "jb_p", "max_dd_%", "notional_at_limit"]].round(4).to_string())

    print("\n" + "=" * 78); print("2. AUTOCORRELATION"); print("=" * 78)
    acf_tab, ac = autocorr_tests(px)
    print(ac[["acf1", "acf2", "acf3", "acf5", "acf_signif_band", "LB_p_lag1",
              "LB_p_lag10"]].round(4).to_string())
    print("\nVariance ratios (<1 revert, >1 trend; |z|>2 significant):")
    print(ac[["VR2", "VR2_z", "VR5", "VR5_z", "VR10", "VR10_z", "VR20",
              "VR20_z"]].round(3).to_string())
    print("\nBest single-window signal (IC = corr with next-day move):")
    print(ac[["best_window", "best_IC", "signal_type"]].round(4).to_string())
    acf_tab.round(4).to_csv(f"{OUT}/2_acf_table.csv")
    ac.to_csv(f"{OUT}/2_autocorr.csv")

    print("\n" + "=" * 78); print("3. VOLATILITY PERSISTENCE"); print("=" * 78)
    vt = vol_tests(px)
    print(vt.round(4).to_string())
    vt.to_csv(f"{OUT}/3_volatility.csv")

    print("\n" + "=" * 78); print("4a. CONTEMPORANEOUS CORRELATION (returns)"); print("=" * 78)
    contemp, ll, gdf, cdf = cross_tests(px)
    print(contemp.round(3).to_string())
    contemp.to_csv(f"{OUT}/4a_contemp_corr.csv")

    print("\n" + "=" * 78); print("4b. TOP LAGGED CROSS-CORRELATIONS (leader_t-k -> follower_t)"); print("=" * 78)
    print(ll.head(25).round(4).to_string(index=False))
    ll.to_csv(f"{OUT}/4b_lead_lag.csv", index=False)

    print("\n" + "=" * 78); print("4c. GRANGER CAUSALITY (p < 0.05)"); print("=" * 78)
    print(gdf[gdf.granger_p_min < 0.05].round(5).to_string(index=False))
    gdf.to_csv(f"{OUT}/4c_granger.csv", index=False)

    print("\n" + "=" * 78); print("4d. COINTEGRATION (levels)"); print("=" * 78)
    print(cdf.head(15).round(5).to_string(index=False))
    cdf.to_csv(f"{OUT}/4d_cointegration.csv", index=False)

    print("\n" + "=" * 78); print("5. CROSS-SECTIONAL MEAN REVERSION"); print("=" * 78)
    panel, per = cross_sectional_reversion(px)
    print(panel.round(4).to_string(index=False))
    print("\nPer-instrument cross-sectionally-demeaned ACF(1):")
    print(per.round(4).to_string())
    panel.to_csv(f"{OUT}/5_xs_reversion_panel.csv", index=False)
    per.to_csv(f"{OUT}/5_xs_reversion_per_instrument.csv")

    print("\n" + "=" * 78); print("6. SEASONALITY & JUMPS"); print("=" * 78)
    sz = seasonality_tests(px)
    print(sz.round(4).to_string())
    sz.to_csv(f"{OUT}/6_seasonality.csv")

    print(f"\nCSV outputs -> {OUT}")


if __name__ == "__main__":
    main()
