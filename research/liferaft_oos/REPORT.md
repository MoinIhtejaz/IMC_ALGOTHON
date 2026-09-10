# Out-of-sample test of the Liferaft strategy

Independent re-test of the regime-conditioned contrarian recommended in
`liferaft_research.pdf`, run against opponents it has never seen, with every
hyperparameter frozen beforehand.

**Verdict: the core survives, two of the five recommended layers do not, and the
crowding limit is far tighter than the original log implies.**

---

## 1. What was done differently

The original results came from six hand-picked rooms built from nine archetypes,
designed alongside the strategy. That is not a test, it is a fit. Five things
were changed:

| | Original | This test |
|---|---|---|
| Engine | `liferaft_sim.py` | re-derived from the spec, 20 unit tests, no shared code |
| Opponents | 9 archetypes | 15 new archetypes, none reused |
| Rooms | 6 curated | sampled at random (Dirichlet mix, size 6-45) |
| Seeds | 10 | 300-400 rooms per cell, disjoint streams per suite |
| Reporting | mean and worst | bootstrap CI, quantiles, P(loss), paired differences |

Hyperparameters were frozen at the recommended values (k=2, warmup 40, probe 6,
min_n 5) before a single held-out room was generated. Nothing was refitted.

Engine checks all pass: majority resolution, abstainers excluded, floor clipping,
no lookahead, reproducibility, notional at decision-time price, and the
hand-computable case of a lone long riding to the floor for exactly -$80,000.

One arithmetic slip found in the original document: it states always-long "nets
$1,500 per two-day cycle" in an oscillating room. A long earns -$5,000 then
+$8,000, so the cycle pays $3,000. The $541,000 annual figure it quotes is
consistent with $1,500 per *day*, so the conclusion is unaffected.

---

## 2. Headline: 300 random held-out rooms

| strategy | mean | 95% CI | median | p05 | worst | P(loss) | days |
|---|---|---|---|---|---|---|---|
| always-flat | 0 | | 0 | 0 | 0 | 0.00 | 0 |
| always-long | 173,617 | [108k, 246k] | -1,000 | -80,000 | -80,000 | 0.55 | 365 |
| always-short | -358,533 | [-453k, -275k] | -3,000 | -2,690,800 | -2,920,000 | 0.57 | 365 |
| floor-option only | 3,067 | [1.8k, 4.5k] | 0 | 0 | 0 | 0.00 | 50 |
| pooled k=0 | -194,840 | [-277k, -111k] | -137,500 | -1,344,100 | -1,545,000 | 0.69 | 266 |
| pooled k=2 | 132,850 | [81k, 190k] | 0 | -60,350 | -707,000 | 0.10 | 96 |
| regime k=0 (raw) | 520,393 | [442k, 601k] | 452,000 | -434,450 | -1,108,000 | 0.23 | 273 |
| **regime k=2 (candidate)** | **588,237** | **[518k, 660k]** | **427,000** | **-10,000** | **-197,000** | **0.07** | **212** |

Both headline claims replicate on opponents that did not exist when they were
made:

- **Regime conditioning is the main P&L effect.** Pooling the year gives
  $132,850; conditioning on yesterday's move gives $588,237, a 4.4x improvement
  with non-overlapping confidence intervals.
- **The confidence discount is close to free tail insurance.** k=0 to k=2 moves
  the mean from $520,393 to $588,237 (overlapping CIs, so treat as flat) while
  cutting P(loss) from 0.23 to 0.07 and the worst room from -$1,108,000 to
  -$197,000.

The magnitudes are lower than the original ($796,400 mean, -$28,000 worst). The
direction and the ranking hold.

---

## 3. Sensitivity: plateau, not spike

The point of this sweep is not to find the best k. Picking one here would be the
overfitting under test. The question is whether k=2 sits on a plateau.

| k | mean | worst | P(loss) | days |
|---|---|---|---|---|
| 0.0 | 531,740 | -868,000 | 0.22 | 274 |
| 0.5 | 586,540 | -297,000 | 0.20 | 242 |
| 1.0 | 598,672 | -314,000 | 0.12 | 228 |
| 1.5 | 597,424 | -232,000 | 0.10 | 220 |
| **2.0** | **597,396** | **-197,000** | **0.07** | **213** |
| 2.5 | 593,220 | -156,000 | 0.05 | 205 |
| 3.0 | 580,848 | -116,000 | 0.04 | 198 |
| 4.0 | 551,080 | -89,000 | 0.03 | 181 |
| 6.0 | 491,764 | -60,000 | 0.02 | 152 |

Mean is flat from k=1 to k=3 (spread under 3%) while tail risk falls
monotonically. This is the healthiest possible shape: the parameter is not
load-bearing for the mean, it is a risk dial, and any value in [1, 3] works.
`min_n` is likewise inert from 2 to 15. Neither is fitted.

---

## 4. Where the strategy actually earns

**Not from the floor.** Attribution over 300 rooms: 99.4% of P&L comes from live
days, 0.6% from floor days. Only 25% of rooms ever reach the floor. The floor
rule is correct and free, but it is not the strategy. Removing it changes the
mean by 0.003% and P(loss) from 0.07 to 0.10; keep it as cheap insurance, not as
a source of return.

**Not from exploiting robot opponents.** The most likely artefact was that the
edge existed only against deterministic archetypes. Splitting the pool:

| opponent pool | candidate mean | P(loss) |
|---|---|---|
| all 15 archetypes | 597,396 | 0.07 |
| **stochastic / adaptive only (7)** | **709,020** | **0.05** |
| deterministic only (8) | 608,288 | 0.04 |

The edge is *stronger* against randomised, adaptive opponents. This is the single
most reassuring result in the test and it directly answers the original log's own
"deterministic rooms flatter the strategy" caveat.

**Not manufactured from noise.** A true zero-edge null was built: the room votes
as a block with P(long) = 8/13 exactly, so E[move] = 0 and every action has zero
expectation, with no regime structure to find.

| strategy in the null room | mean | worst | P(loss) | days traded |
|---|---|---|---|---|
| candidate (k=2) | 28,182 | -54,000 | 0.15 | **20** |
| regime k=0 | 19,835 | -312,000 | 0.42 | **270** |
| always-long | 40,595 | -80,000 | 0.40 | 365 |

The candidate trades 20 days out of 365 when there is nothing to find, against
270 for the undiscounted version. The small positive mean is legitimate: 4% of
null rooms drift to the floor by luck, and the floor truncates losses, which is
why always-long also prints positive in a zero-EV room. The discount does exactly
what it claims to do.

---

## 5. Where it breaks

### Crowding, and it is worse than reported

Exact copies of the candidate added to a 20-team room:

| clones | mean | P(loss) |
|---|---|---|
| 0 | 488,325 | 0.07 |
| 1 | 276,858 | 0.30 |
| 2 | 104,050 | 0.54 |
| **3** | **-53,283** | **0.72** |
| 5 | -267,825 | 0.88 |
| 8 | -298,417 | 0.88 |

**Three other teams running similar logic is enough to make this lose money.**
The original log tested 1, 3, 6 and 10 clones and read the result as a tail risk.
On a finer grid the break-even sits between 2 and 3 clones out of 20. Given that
regime conditioning is the natural conclusion for any team that thinks about the
problem for an afternoon, this is not a remote scenario.

### Small rooms

| opponents | mean | P(loss) | worst |
|---|---|---|---|
| 3 | 77,692 | 0.36 | -240,000 |
| 5 | 180,458 | 0.23 | -248,000 |
| 10 | 375,292 | 0.15 | -408,000 |
| 20 | 574,375 | 0.05 | -72,000 |
| 80 | 785,708 | 0.00 | 0 |

Performance is monotone in room size, because in a small room our own vote
decides the day and the game becomes self-defeat. If most teams skip the
instrument, the effective room is small. The "mostly abstains" adversarial room
gives P(loss) 0.42 and a worst case of -$246,000.

### Where it is fine

In the two rooms that destroy always-long, the candidate simply declines to play:
against a room herding long it trades zero days for zero P&L while always-long
loses exactly -$80,000 on every seed; in an all-clone room it also sits out. Not
trading is a real result and the ability to return zero is what produces it.

---

## 6. Two of the five recommended layers fail

Stage 1 suggested the warmup and probe layers cost money. Acting on that using
the same rooms would be circular, so the hypothesis was tested once on a fresh
seed stream (400 rooms, base seed 200,000, untouched by any earlier stage),
paired room by room:

| config | mean | worst | P(loss) | paired diff vs recommended |
|---|---|---|---|---|
| recommended (warmup 40, probe 6) | 545,092 | -210,000 | 0.07 | reference |
| no probe | 656,872 | -247,000 | 0.07 | **+111,780** [+98,840, +125,608] |
| no warmup | 577,742 | -210,000 | 0.10 | **+32,650** [+26,412, +39,238] |
| **no probe, no warmup** | **697,892** | -264,000 | 0.11 | **+152,800** [+134,990, +171,137] |
| k=0, recommended layers | 469,480 | -1,103,000 | 0.25 | -75,612 [-96,339, -55,560] |

All intervals exclude zero.

The probe layer costs about **$112,000 a year** and the warmup about **$33,000**,
together roughly 28% of P&L, for a 4-point increase in P(loss). Both were
justified in the original log by reasoning rather than by an ablation: probe days
were meant to keep uncontaminated reads flowing, and warmup to avoid trusting a
thin estimate. Neither survives measurement. The estimator already handles thin
samples through the standard-error term, so warmup duplicates work k is doing,
and one vote in twenty contaminates a sample far less than throwing away a sixth
of the year costs.

Layer 3 (k=2) is confirmed in the same run: dropping it costs $75,612 and takes
the worst room from -$210,000 to -$1,103,000.

---

## 6b. Should abstention default to flat or to long?

Worth asking, because on the Round 1 scaffolding series the room goes long on
214 of 364 sided days (q = 0.588, just inside the 0.615 break-even). That is a
real edge for a long of about +$357/day, but daily noise has an SD of $6,399, so
the k=2 haircut correctly rules it undetectable and the strategy sits flat for
the whole year where a constant long would have taken about $130,000.

Since long carries the lower bar, defaulting to long when nothing clears is a
reasonable hypothesis. Tested once on a fresh stream (400 rooms, base seed
400,000, paired):

| variant | mean | p05 | worst | P(loss) | days holding |
|---|---|---|---|---|---|
| **flat-default (shipping)** | **740,062** | **-12,050** | **-297,000** | **0.09** | **254** |
| long-default | 739,998 | -107,150 | -379,000 | 0.24 | 350 |
| long-if-mean-positive | 714,618 | -277,000 | -754,000 | 0.22 | 304 |

Means are indistinguishable (paired difference -$65, interval spans zero) but
flat-default has a third of the loss probability, a far better fifth percentile,
and holds a position on 254 days instead of 350, which hands roughly 100
days x $100k of budget back to the rest of the book. **Keep flat.** The
scaffolding series is one path and not a reason to change anything.

---

## 7. Recommendation

Keep, in priority order:

1. **Long whenever price is at $20,000.** Free, verified never negative. Not a
   source of return (0.6% of P&L) but costless insurance.
2. **Regime-conditioned estimate.** The entire edge. 4.4x over pooling.
3. **k = 2 confidence discount.** Anywhere in [1, 3] is equivalent on mean; 2 to
   3 is the sweet spot on tails. The reason to keep it is what it does in the
   null room, not what it does to the mean.
4. **Flat whenever the discounted edge is not positive.** The ability to return
   zero is what produces every good tail number in this report.

Drop:

- **The 40-day warmup.** Costs $33,000, measured, on fresh seeds.
- **The every-6th-day probe.** Costs $112,000, measured, on fresh seeds.

Unresolved:

- **Crowding is the binding risk and it cannot be fixed inside the strategy.**
  Break-even is under 3 like-minded teams in 20. A deliberate randomisation
  (acting on the discounted edge only some fraction of days, or jittering the
  regime definition) is the only obvious mitigation and was not tested here.
- **The floor result still rests on the grader booking the clipped move.** The
  live pricing code has not been supplied. Given the floor contributes 0.6% of
  P&L, the exposure is small either way, which is itself a useful finding: the
  strategy no longer depends on that assumption.
- Every number here is still conditional on invented opponents. Fifteen new
  archetypes and randomised rooms is a broader base than six curated ones, but
  it is not a calibrated prior over what other teams will actually submit.

Implementation note carried over and worth repeating: cast positions with
`int()`. The grader uses `type(x) != type(1)`, so a numpy integer is silently
zeroed.

---

## 7b. Shipped code

`trader_interface/algorithm.py` now runs this strategy in `_sig_liferaft`, with
`LIFERAFT_K = 2.0`, `LIFERAFT_MIN_N = 5`, floor long, and no warmup or probe.

`verify_shipped.py` imports the real `Algorithm` class and drives it through the
simulator: **200 rooms, zero mismatches**, identical actions and identical P&L to
the tested reference. Edge cases (empty history, one price, at and below the
floor, a permanently flat series, instrument missing) all return a legal value,
and the returned position is a builtin `int`, which the grader's
`type(x) != type(1)` check requires.

Local backtest effect: none of it is Liferaft P&L, which
`NO_LOCAL_PNL_INSTRUMENTS` forces to zero. It is entirely budget the estimator
stops consuming. On the scaffolding series the haircut never clears, so Liferaft
holds nothing all year and the full ~$100k/day is released.

**That release had a consequence worth catching.** Thrifted Jeans is last in
`BUDGET_PRIORITY`, so it absorbed most of the freed budget and went from $3,842
of mean notional on 66 days to $42,300 on 351 days, an 11x increase. It then
supplied $88,148 of the $110,397 apparent gain. A "spend the leftovers" argument
does not survive that change in size, so Jeans was re-tested at the new
allocation: shuffle its daily returns 200 times, preserving distribution and
drift and destroying only ordering, rerun the whole book each time
(`jeans_permutation.py`).

| | total P&L |
|---|---|
| real ordering | $656,757 (96.5th percentile of null, p = 0.040) |
| shuffled null, mean | $570,010 |
| Jeans switched off | $568,609 |
| null 5th / 95th percentile | $488,938 / $645,380 |

Trading a structureless Jeans and not trading it at all pay the same. What keeping
it buys is a +/- $78k noise band for an expected gain indistinguishable from
zero, on a p = 0.040 result that is one of roughly 43 tests run on this
instrument and nowhere near the Bonferroni threshold of 0.0012.

**Jeans is now switched off.** Final book:

| variant | total | Sharpe | max drawdown |
|---|---|---|---|
| old (Liferaft always long, Jeans on) | 546,360 | 14.39 | -4,693 |
| new estimator, Jeans on | 656,757 | 12.47 | -12,544 |
| **new estimator, Jeans off (shipping)** | **568,609** | **14.85** | **-4,898** |

Best Sharpe of the three, roughly a third of the drawdown, and $22,249 ahead of
the previous book. Sharpe is the competition tie-breaker. The freed budget now
goes to Sausage Sizzle, MenuDash and Bread rather than to a series that cannot be
told apart from its own shuffle.

The general lesson generalises past this instrument: **freeing budget in one
place silently resizes everything downstream of it in the priority list.** Any
future change to Liferaft's participation rate should be followed by re-checking
what the residual claimant grew into.

---

## 7c. Budget safety

The grader's rule is `sum(abs(position * decision_time_price)) > 600000`, and a
breach zeroes **the entire book** for that day rather than trimming the offending
line. One dollar over costs the whole day.

The allocator previously guarded this with `BUDGET_SAFETY = 0.97`, a static 3%
haircut costing $18,000 of capacity daily, which was also not a guarantee: it
sized against its own running total and never re-checked the finished book. It is
replaced by three things.

**Exact accounting.** A $10 absolute reserve instead of a 3% multiplicative one.
The only error worth guarding against is float non-associativity between our sum
and the grader's, which for nine terms of order 1e5 is about 1e-10 dollars. Ten
dollars is eleven orders of magnitude of headroom for 0.0017% of the book.

**Dynamic claiming.** Budget is taken greedily in priority order against the
*live* remaining balance, so capacity a flat or cheap instrument does not use
flows automatically to whatever comes next. An instrument that cannot afford one
unit is skipped rather than aborting the pass, so cheaper instruments below it
still get funded.

**A hard enforcement pass.** `_enforce_budget` recomputes the finished book the
grader's way and trims from the bottom of the priority list until it is genuinely
under the cap. It runs unconditionally, so it stays correct even if the allocator
above it is later changed or broken.

`test_budget.py` covers:

| test | result |
|---|---|
| all 365 Round 1 days: breaches / bad types / limit violations | 0 / 0 / 0 |
| peak utilisation | $545,248.50 (90.87% of cap) |
| adversarial price paths (10x, 100x, near-zero, one instrument enormous, floor, cheap high-limit) | all legal, worst 99.8% of cap |
| enforcement pass on a $1,980,000 book | repaired to $599,300, Sizzle untouched, Jeans shed first |
| single position alone exceeding the cap | zeroed |
| saturating demand | $599,989 of $600,000 used, no breach |
| funding Liferaft under a full book | displaces $99,999 from the bottom, Sizzle held |
| price shock sweep 1x to 200x | unit counts shrink, never breaches |
| NaN / inf / out-of-range signal values | legal book |
| empty price history | flat book |

**One real bug fixed.** An empty price series raised `IndexError` inside
`get_positions`, which the grader does not catch, so it would have taken the run
rather than one instrument. Round 1 always supplies data from day 0 and nothing
in the contract promises Round 2 will. Every signal now guards through `_ready()`.

Round 1 P&L is unchanged at $568,609, because peak utilisation is 90.9% and the
old 0.97 margin was never actually binding on this data. The change buys nothing
here and removes a live risk in Round 2, where higher prices would have made that
margin throttle the book for no reason. Worth noting separately: at peak there is
still $54,751 of unused capacity, so the binding constraint on this book is
position limits and flat signals, not budget.

---

## 8. Reproducing

```
python3 verify_engine.py          # 20 spec checks, must pass first
python3 verify_shipped.py         # shipped algorithm.py == tested strategy
python3 test_budget.py            # budget cap, position validity, edge cases
python3 jeans_permutation.py      # Thrifted Jeans shuffled-returns null
python3 stage1_headline.py        # headline table
python3 stage2_sensitivity.py k | warmup | probe | minn
python3 stage3_adversarial.py adv | selfplay | size
python3 stage4_decompose.py pools | attrib | null
python3 stage5_null.py            # true zero-edge null
python3 stage6_confirm.py         # fresh-seed confirmation
python3 stage7_tilt.py            # flat vs long default, fresh seeds
```

All stages are deterministic given their seed bases, which are disjoint by
construction: headline/sensitivity 10,000; adversarial 30,000; self-play 50,000;
room size 70,000; null 80,000; confirmation 200,000; equivalence 300,000;
tilt test 400,000.
