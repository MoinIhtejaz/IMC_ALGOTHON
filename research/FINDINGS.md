# AlgoJam 3 — Round 1 structural analysis

365 days × 9 instruments. Every IC below is `corr(signal_t, price_change_{t+1})`,
computed causally, and split-half tested (first 182 days vs last 182). A signal is
marked **USE** only if |t| > 2 **and** both halves have the same sign.

Scripts: `structure_tests.py` (broad diagnostics) → `deep_dive.py` (per-instrument
follow-ups) → `verify.py` (kills the artefacts). Raw tables in `out/`.

---

## 1. Structure — what each series actually is

| Instrument | ADF p | Hurst | Half-life | Drift t | Ann vol | Verdict |
|---|---|---|---|---|---|---|
| UQ Dollar | 0.10 | **0.008** | **0.72d** | -0.01 | 9.5% | Hard OU peg |
| Sausage Sizzle | 0.49 | 0.72 | 152d | 2.52 | 4.1% | Deterministic cost function |
| MenuDash | 0.16 | 0.52 | 22d | 0.47 | 16.0% | Rounded noisy read of the same cost |
| Boat Party | 0.07 | 0.55 | 21d | -0.03 | 34.8% | Seasonal trend + overreaction |
| Fintech Token | 0.56 | 0.58 | 129d | -1.11 | 37.8% | Random walk w/ vol regimes |
| Bread | 0.40 | 0.51 | 66d | 0.32 | 11.2% | Random walk, weak trend |
| Sausage | 0.84 | 0.56 | 134d | 2.23 | 9.9% | Drifting random walk |
| Thrifted Jeans | 0.15 | 0.58 | 59d | 0.90 | 86.1% | Drifting random walk |
| Liferaft | — | 0.45 | — | 1.06 | 73.8% | Not a price process (see §6) |

Two instruments are not random: **UQ Dollar** (Hurst 0.008 — maximally
anti-persistent) and **Sausage Sizzle** (Hurst 0.72 — but that is the ingredient
trend showing through, not tradeable trend). Everything else sits at Hurst ≈ 0.5.

Tails: only **Boat Party** (kurtosis 9.5, JB p<0.001) and Liferaft are non-normal.
The rest pass Jarque-Bera. Boat Party's fat tail is the overreaction event.

Discreteness matters for two: **MenuDash** trades on a $0.01 grid, 22.5% of days
unchanged, range $1.70–$2.00. **Sausage** is 12.6% unchanged. Signals on these need
a deadband or you trade noise.

---

## 2. Autocorrelation

Significance band at n=364 is ±0.103.

| Instrument | ACF(1) | ACF(2) | LB p (lag 10) | VR(10) | Read |
|---|---|---|---|---|---|
| UQ Dollar | **-0.492** | -0.012 | <0.001 | **0.109** | Violent 1-day reversion |
| Boat Party | **-0.168** | -0.043 | 0.002 | 0.890 | Overreaction |
| Fintech Token | **-0.132** | 0.064 | 0.008 | 1.257 | Weak 1-day reversion |
| Sausage Sizzle | 0.085 | **0.155** | <0.001 | **2.183** | Trend (inherited from cost) |
| Sausage | 0.091 | 0.090 | 0.002 | 1.752 | Mild trend |
| Bread | 0.064 | 0.031 | 0.234 | 1.560 | Mild trend |
| MenuDash | -0.042 | -0.027 | 0.362 | 0.632 | Reversion in levels, not returns |
| Thrifted Jeans | -0.051 | 0.023 | 0.077 | 1.266 | Nothing |
| Liferaft | 0.039 | -0.026 | 0.215 | 0.992 | Nothing |

Variance ratios split the board cleanly: **VR < 1 → reversion** (UQ Dollar 0.11,
MenuDash 0.63, Boat Party 0.89), **VR > 1 → trend** (Sizzle 2.18, Sausage 1.75,
Bread 1.56). Note the VR z-stats are all small — with 365 days the Lo-MacKinlay
test has little power, so treat VR as a directional hint and rely on the IC
split-half test for the actual decision.

---

## 3. Volatility persistence

| Instrument | ARCH-LM p | GARCH α | GARCH β | α+β | Vol half-life |
|---|---|---|---|---|---|
| **Fintech Token** | **0.004** | 0.035 | 0.951 | **0.986** | **47.5d** |
| **UQ Dollar** | **<0.001** | 0.463 | 0.078 | 0.541 | 1.1d |
| Sausage Sizzle | 0.30 | 0.006 | 0.973 | 0.979 | 32.5d |
| Bread | 0.64 | 0.015 | 0.964 | 0.979 | 33.1d |
| MenuDash | 0.34 | 0.000 | 0.984 | 0.984 | 41.8d |
| Thrifted Jeans | 0.82 | 0.000 | 0.899 | 0.899 | 6.5d |
| Sausage / Liferaft / Boat Party | >0.5 | ~0 | ~0.50 | ~0.50 | ~1d |

Only two instruments have statistically real ARCH effects.

**Fintech Token is the volatility-persistence instrument.** |return| ACF(1) = 0.089,
ACF(10) = 0.125 (still positive at lag 10 — long memory), rolling-20d vol ranges
7.4 → 19.7 (2.7×) with ACF(1) = 0.967. Vol is highly forecastable even though
direction is not. Two uses: (a) size positions inversely to forecast vol, (b) the
vol-scaled reversion signal beats the raw one (IC 0.151 vs 0.133).

The other high α+β values (Sizzle, Bread, MenuDash) are **spurious** — ARCH-LM says
p > 0.3. GARCH is fitting the slow cost trend as persistence, not genuine clustering.
Don't act on those.

UQ Dollar's α=0.46/β=0.08 is a different animal: shock-driven, one-day memory. It
means a big deviation today implies a big move tomorrow, which is exactly the
reversion trade.

---

## 4. Lagged correlation and lead-lag

Contemporaneous return correlations are all |ρ| < 0.13 — the instruments are
essentially independent same-day. **All the structure is in the lags.**

| Leader (t-k) | Follower (t) | Lag | Corr | Granger p |
|---|---|---|---|---|
| **Bread** | **Sausage Sizzle** | 1 | **+0.709** | <0.001 |
| **Sausage** | **Sausage Sizzle** | 1 | **+0.607** | <0.001 |
| Liferaft | Bread | 5 | -0.148 | ns |
| Bread | Sausage | 5 | +0.137 | ns |
| Sausage Sizzle | Sausage | 4 | +0.136 | ns |

Only the two Sizzle relationships clear the noise floor (±0.103); everything below
row 2 is indistinguishable from zero. Granger confirms: Bread→Sizzle and
Sausage→Sizzle at p<0.001, the next-best (Sausage→Boat Party, p=0.031) is what you'd
expect from 72 tests at 5%.

**The recipe, fitted:**

```
Sizzle_t = 18.95 + 0.0742 · Bread_{t-1} + 1.7268 · Sausage_{t-1}     R² = 0.696
```

Lag-1 beats same-day (R² 0.696 vs 0.685), confirming yesterday's shopping. Your
current priors (0.07692, 1.76921) are within 4% — good.

The residual is the **labour cost**: mean 18.95, sd 0.66, but daily change sd only
0.0375 with ACF(1) = 0.50. It barely moves and it's autocorrelated. So:

> **Today's Bread and Sausage prices are already printed, which means tomorrow's
> Sizzle price is 85% determined before the day opens.** IC of the known ingredient
> move vs tomorrow's Sizzle move = **0.922**. Add the labour drift term and it goes
> to **0.960**.

This is the single largest edge on the board and it survives split-half cleanly
(0.966 / 0.953).

**Cointegration:** UQ Dollar pairs with everything at p<0.001 — that's an artefact
of it being stationary on its own, not a real pair. The genuine ones are
Thrifted Jeans ~ Sausage Sizzle (p=0.0013, spread half-life 17.5d) and
Fintech Token ~ Bread (p=0.0091, half-life 18.1d). Both look like coincidence given
36 pairs tested, and neither has an economic story. Skip.

---

## 5. Cross-sectional mean reversion — **rejected**

Standardising each instrument's return, demeaning across the panel each day, then
regressing on the 1-day lag:

| Panel | XS ACF(1) | t |
|---|---|---|
| All 9 | -0.093 | -5.32 |
| Ex UQ Dollar | -0.042 | -2.26 |
| Ex UQ Dollar & Liferaft | -0.066 | -3.31 |
| Ex the 4 with own structure | **-0.023** | **-0.98** |

The headline t = -5.3 looks compelling but it is **UQ Dollar's -0.43 own-ACF
leaking into the panel**. Strip out the instruments with their own documented
reversion and the effect vanishes (t = -0.98).

Per-instrument demeaned ACF(1) confirms it: UQ Dollar -0.430, Boat Party -0.148,
Sizzle -0.126, Fintech -0.103, and then Bread -0.014, Sausage -0.008,
Jeans -0.025 — noise.

**There is no cross-sectional reversal factor to trade.** Don't build a
rank-and-reverse book. Trade each instrument on its own model. This also means
you can't diversify your way to a higher Sharpe — the near-zero contemporaneous
correlations already give you that for free.

---

## 6. Seasonality, jumps, Liferaft

**FFT:** every instrument's top periodogram peak is 365 or 182.5 days, i.e. the
sample length itself — that's the trend, not seasonality. No weekly or monthly
cycle anywhere (ANOVA on period 5, 7, 30 all p > 0.05 except two marginal hits
consistent with multiple testing).

**Boat Party is the exception**: 50% of its power at period 182.5 = two semesters.
83.8% of its variance is smooth trend, 7.7% residual.

⚠️ **Correcting a trap I hit:** measuring the seasonal slope with a *centred*
rolling mean gives IC 0.258, but that uses future data. Done causally with a
trailing mean the slope IC collapses to **0.029 (t=0.53)**. And when I fit the
day-of-year shape on days 0–181 and apply it to days 182–364, the IC is
**-0.118** — it flips sign.

**This means the hard-coded `BOAT_SEASONAL` table in `algorithm.py` is not
validated and may hurt you in Round 2.** Round 1's two semesters aren't copies of
each other; a fixed calendar table fitted on Round 1 has no evidence of
transferring. The reliable part of Boat Party is the pure short-horizon reversion
(w=3, IC 0.181, stable). Consider dropping the seasonal term, or use a causal
trailing-mean slope so it adapts to whatever Round 2's calendar does.

**Jumps:** only Boat Party has any (3 moves > 4σ, 7 > 3σ). After a big down move
the next day averages +0.243; after a big up move, +0.115. Both positive — so the
snap-back is asymmetric and mostly happens after crashes.

**Liferaft:** the price moves take exactly two values — **-5000 (214 days) and
+8000 (150 days)**, never anything else, never flat. This is a pure voting game
payoff, not a price process. Round 1's path is the Round 1 room's behaviour and
carries **no information** about Round 2's room. Sign ACF(1) = 0.039, mean run
length 2.14 — indistinguishable from independent flips. The contrarian signal
your algorithm uses tests at IC -0.039 (t=-0.74), **rejected**.

The only defensible play is the payoff asymmetry: long wins +8000, short wins
+5000, so long is right whenever P(majority long) < 8000/13000 = 0.615. Round 1's
observed rate was 214/364 = **0.588** — below the breakeven, so **stay long**. But
treat that as a prior, not a signal.

---

## 7. Validated signal table

Everything that survived. `IC_h1`/`IC_h2` are the split halves.

| Instrument | Model | IC | t | h1 | h2 |
|---|---|---|---|---|---|
| Sausage Sizzle | known ingredient move + 10d labour drift | **0.960** | 64.3 | 0.966 | 0.953 |
| UQ Dollar | OU reversion to fitted peg 99.94 | **0.694** | 18.3 | 0.726 | 0.680 |
| MenuDash | causal rolling fair-value gap to labour | 0.280 | 4.90 | 0.301 | 0.265 |
| Boat Party | reversion w=3 (+ causal trailing slope) | 0.206 | 3.88 | 0.141 | 0.290 |
| Sausage | momentum w=11 | 0.180 | 3.43 | 0.262 | 0.073 |
| Bread | momentum w=10 | 0.136 | 2.58 | 0.132 | 0.136 |
| Fintech Token | reversion w=2, vol-scaled | 0.133 | 2.54 | 0.059 | 0.243 |

**Rejected:**

| Instrument | Model tested | IC | Why |
|---|---|---|---|
| Thrifted Jeans | momentum w=15 | 0.097 | t=1.82, below threshold |
| Fintech Token | reversion w=5, 7, 10 | -0.016 to -0.062 | **sign flips between halves** |
| Liferaft | contrarian to last move | -0.039 | t=-0.74 |
| Boat Party | fixed day-of-year table | -0.118 OOS | doesn't transfer |
| All | cross-sectional reversal | -0.023 | t=-0.98 ex-UQD |

---

## 8. Recommended models

**Sausage Sizzle — deterministic forecast, not a signal.** Don't use momentum
w=13 (IC 0.263) when you have a 0.96-IC forecast available. Compute
`ΔSizzle_{t+1} = 0.0742·ΔBread_t + 1.7268·ΔSausage_t + drift(labour, 10d)`
and take the full position on its sign. Re-fit A and B online — your smoothness-
minimisation refit is a reasonable approach, but a rolling OLS of Sizzle on lagged
Bread/Sausage is more direct and gets R²=0.70 immediately.

**UQ Dollar — Ornstein-Uhlenbeck.** Fitted κ = 0.963, half-life 0.72 days, peg
99.94, residual σ = 0.43. κ ≈ 1 means it fully reverts in one day. Size
*proportionally* to the deviation rather than using a binary deadband — the bucket
analysis shows hit rate scales from 49% (|dev|<0.05) to 92-95% (|dev|>0.33). Your
current 0.15 deadband throws away the 0.05–0.15 bucket which still hits 59-72%.
Scale position ∝ clip(dev/0.5, -1, 1) and you capture the gradient.

**MenuDash — rolling cointegration to the labour cost.** MenuDash level correlates
0.931 with implied labour, R² = 0.867, gap half-life 2.94 days. Your current 60-day
rolling regression is right; the causal version tests at IC 0.280 (vs 0.135 for
naive mean-reversion), so keep it. Add a deadband of ~1 tick ($0.01) since 22.5% of
days don't move — trading a sub-tick gap is pure churn. Note the naive turnover was
12.7M units, by far the worst on the board.

**Boat Party — short-horizon reversion only.** w=3 mean reversion, IC 0.181,
stable. Drop or de-weight the hard-coded seasonal table. If you want the trend,
use a *causal* trailing-21d slope, which at least adapts (the combined signal tests
at 0.206, marginally better than reversion alone). This is also the best
PnL-per-dollar-of-budget instrument (1.998), so it should sit high in your budget
priority — it currently does.

**Fintech Token — vol-scaled 1-day reversion.** Your current signal averages
windows 5, 7 and 10, and **all three are rejected** — they flip sign between halves
(h1 ≈ -0.15, h2 ≈ +0.17). Only w=2 is stable (IC 0.133). Switch to a 1–2 day
reversion divided by a GARCH or rolling-20d vol estimate (IC 0.151). The vol
persistence (α+β=0.986, half-life 47d) is real and belongs in the *sizing*, not
the direction.

**Bread & Sausage — keep momentum, but small.** Both stable at IC 0.136/0.180,
and the edge is genuine time-series momentum, not drift capture (drift-removed ICs
are identical to raw). But they're the two worst PnL-per-budget instruments (0.301,
0.399) and Sausage's naive version turns over 485k units. Fund them last.

**Thrifted Jeans — hold the partial long.** Momentum w=15 doesn't validate
(t=1.82). Drift t = 0.90 over one year is not proof of drift either. Your 0.6
partial long is a defensible compromise, though be aware it's a bet, not a signal —
86% annualised vol on a 119% Round 1 gain could just as easily be -50% in Round 2.

**Liferaft — stay long, ignore the history.** No exploitable structure. Long is
favoured by the +8000/-5000 asymmetry as long as fewer than 61.5% of teams go long.
Your adaptive contrarian logic is fitting noise (IC -0.039); the shrinkage toward
an even room makes it mostly harmless, but simple constant-long is at least as good
and won't get whipsawed.

**Budget note:** naive full-limit positions on all 9 need $693k against a $600k cap,
so the priority ordering does bind. On PnL per dollar of budget the order is
Boat Party (2.00) > Thrifted Jeans (1.79) > Fintech (1.48) > UQ Dollar (0.92) >
Liferaft (0.68) > Sausage (0.40) > Bread (0.30) > MenuDash (0.30) > Sizzle (0.26).
Your current `BUDGET_PRIORITY` puts Sizzle 6th and MenuDash 5th — but Sizzle now has
by far the highest-confidence signal (IC 0.96 vs 0.13-0.28 for the rest). Low PnL
per dollar with near-certain direction is worth more than the raw ratio suggests
once you account for the risk; consider promoting it.

---

## Caveats

- One year, 365 observations. A t-stat of 2.5 on 350 points is not strong evidence;
  the split-half test is the more informative column and I'd weight it over the IC.
- I tested ~36 cointegration pairs and 72 Granger pairs without a multiple-testing
  correction. Only the two Sizzle relationships (p < 1e-10) survive a Bonferroni
  threshold. Treat the rest as noise, which is how I've reported them.
- ICs here are gross of the budget constraint and assume you take the full limit on
  the sign. Real PnL will be lower once positions compete for the $600k.
- Round 2 is a different draw from the same generators. The *structure* (peg,
  recipe, rounding) should transfer; the *fitted constants* (drift rates, the
  seasonal table, PnL rankings) may not.
