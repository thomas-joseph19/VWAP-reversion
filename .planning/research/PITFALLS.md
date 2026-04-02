# Domain Pitfalls

**Domain:** NQ Futures VWAP Reversion Backtesting
**Researched:** 2026-04-01
**Confidence:** HIGH (core VWAP/futures mechanics), MEDIUM (performance/execution modeling)

---

## Critical Pitfalls

These cause incorrect results, silent data corruption, or invalidate the entire backtest.

### Pitfall 1: VWAP Standard Deviation Uses the Wrong Formula

**What goes wrong:** Developers compute VWAP bands using `pandas.rolling().std()` on price, or use a rolling window of N bars. VWAP standard deviation is actually the *volume-weighted expanding standard deviation of price from VWAP*, computed cumulatively from session start — not a rolling window of recent prices.

**Why it happens:** The VWAP σ formula is unusual. Most standard deviation implementations use a fixed rolling window. VWAP σ expands from the anchor point (session open) and weights each observation by volume. The formula is:

```
σ_vwap = sqrt( Σ(volume_i × (price_i - VWAP)²) / Σ(volume_i) )
```

where the summation runs from session start to the current bar. Using `rolling(window=N).std()` or an unweighted expanding std produces entirely different band widths.

**How to avoid:** Implement VWAP σ from scratch using cumulative sums. Maintain running accumulators for `Σ(v × p)`, `Σ(v × p²)`, and `Σ(v)`. Derive σ as `sqrt(Σ(v×p²)/Σ(v) - VWAP²)`. Validate against a known platform (TradingView, NinjaTrader) on the same data for at least 5 sessions.

**Warning signs:** Band widths that don't expand throughout the session, bands that are implausibly narrow or wide compared to visual price action, σ values that don't match the project's reference statistics (median max deviation ~2.0σ).

**Phase to address:** VWAP computation phase — must be correct before any signal generation.

---

### Pitfall 2: Wrong Session Anchor for VWAP Reset

**What goes wrong:** Daily VWAP is anchored to midnight UTC, or to the Globex session open (6:00 PM ET prior day), or to an arbitrary time. The strategy explicitly targets the first 1-2 hours after RTH open, so the VWAP anchor point determines what "extended from VWAP" means — different anchors produce different VWAP values and different σ readings.

**Why it happens:** The data is in UTC. CME Globex runs nearly 23 hours. There is no single "correct" answer — different traders anchor differently. But the strategy model being tested uses specific VWAP anchoring conventions that must be matched precisely.

**How to avoid:** Clarify and document the exact anchor convention before writing any code:
- **Daily VWAP for RTH trading:** Anchor at RTH open (9:30 AM ET → UTC varies by DST). Include only RTH volume in the daily VWAP calculation, or include overnight volume — this is a deliberate design decision.
- **Weekly VWAP:** Anchor at the start of the week's first RTH session (Monday 9:30 AM ET). Roll across daily boundaries without resetting.
- **Monthly VWAP:** Anchor at the first RTH session of the calendar month.

**Warning signs:** VWAP value at 9:31 AM ET is not equal to the first trade price (if anchored at RTH open, VWAP should equal the first RTH trade for the first bar). Weekly/monthly VWAP values don't align with charting platform references.

**Phase to address:** VWAP computation phase — anchor convention must be defined in the discuss/plan stage.

---

### Pitfall 3: DST Transitions Corrupt Session Boundaries

**What goes wrong:** The RTH window (9:30-11:30 ET) shifts by one hour in UTC twice per year. Code that hardcodes `13:30 UTC` for RTH open works during EST but produces a 1-hour offset during EDT (where RTH open is `13:30 UTC`... wait, no: EST = UTC-5 → 9:30 AM ET = 14:30 UTC; EDT = UTC-4 → 9:30 AM ET = 13:30 UTC). If the code uses the wrong offset for even a few roll-over days, session filtering silently includes/excludes the wrong data.

**Why it happens:** The data spans Feb 2021 to Nov 2023 — six DST transitions. Python's `pytz` library has a known design flaw: arithmetic across DST boundaries produces wrong results because `pytz.tzinfo` objects don't update when datetime values change. Even `zoneinfo` requires careful handling of wall-time vs absolute-time semantics.

**How to avoid:**
1. Use `zoneinfo.ZoneInfo('US/Eastern')` (not `pytz`) for all timezone conversions.
2. Convert all UTC timestamps to US/Eastern at load time: `ts.dt.tz_localize('UTC').dt.tz_convert('US/Eastern')`.
3. Never hardcode UTC offsets — always derive session boundaries from timezone-aware datetimes.
4. Test explicitly on DST transition dates: 2021-03-14, 2021-11-07, 2022-03-13, 2022-11-06, 2023-03-12, 2023-11-05.
5. On Windows: install `tzdata` package for up-to-date timezone rules.

**Warning signs:** Sudden 1-hour shift in VWAP patterns around March/November. Trade count anomalies on DST dates. RTH window captures pre-market or misses the open on specific dates.

**Phase to address:** Data loading/parsing phase — timezone handling must be established in the foundational data pipeline.

---

### Pitfall 4: Front-Month Identification Breaks at Roll Dates

**What goes wrong:** The backtester uses the wrong contract as "front month" during the roll window (typically Thursday before expiration Friday, but volume migration starts earlier). For ~1-2 weeks around each quarterly roll, the back-month contract carries more volume than the expiring front-month. If the code always selects the nearest expiration as front month, it trades a dying contract with deteriorating liquidity and widening spreads.

**Why it happens:** CME equity index roll dates follow a specific pattern — the Monday before the third Friday of the expiration month (H/M/U/Z). But volume migration is gradual: institutional volume shifts to the new contract over several days. The data contains multiple NQ contracts per file (e.g., NQH3, NQM3, NQU3, NQZ3 plus spreads), and naive symbol sorting or nearest-expiration logic fails during the transition.

**How to avoid:**
1. Use a **volume-based roll rule**: for each day, select the NQ contract with the highest total daily volume. This naturally follows the institutional migration.
2. Alternatively, use a **hard roll date table** (known CME roll dates for 2021-2023) and switch on a fixed date. The hard table is simpler but less adaptive.
3. **Validate roll dates** by checking that the selected contract's symbol changes exactly at the expected quarterly boundaries.
4. During the data period (2021-2023), there are approximately 11-12 quarterly rolls. Verify each one manually.

**Warning signs:** Price jumps of 50-200 points on a single bar that don't appear on a charting platform. Sudden volume drops to near-zero on "front month." Two contracts showing high volume simultaneously.

**Phase to address:** Data loading/parsing phase — front-month filtering is foundational.

---

### Pitfall 5: Look-Ahead Bias in VWAP and Signal Calculation

**What goes wrong:** The VWAP or σ band at time T uses data from time T+1 or later. This can happen through:
- Using `pandas.resample()` with default settings (which can include future data in the current bin).
- Computing VWAP for the full session first, then "replaying" it — the VWAP at 10:00 AM incorrectly reflects 10:01+ data.
- Using end-of-bar data for mid-bar decisions (price at the end of a 1-second bar to trigger entry within that same bar).
- Volume profile levels computed over the full day, then used to make intra-day decisions.

**Why it happens:** It's computationally convenient to compute indicators over complete arrays and then filter. The 1-second resolution creates a false sense of safety ("it's only 1 second of look-ahead"), but even 1 second matters at NQ tick sizes.

**How to avoid:**
1. Implement VWAP as a **strictly cumulative, causal computation**: at each timestamp, only data from prior timestamps contributes.
2. For volume profiles used as "structural levels," compute them from **prior completed sessions only** — never include today's developing profile.
3. HTF (180-day rolling) volume profiles must use data strictly before the current session.
4. Signal detection at bar T should use indicator values computed through bar T-1, with entry simulated at bar T+1 at the earliest.
5. Add an assertion: for any signal at time T, verify that all input data has timestamps < T.

**Warning signs:** Backtest performance that degrades when you add a 1-bar delay to all entries. Win rates that exceed the reference statistics (55-60% mechanical, up to 70% at key levels) by a suspicious margin.

**Phase to address:** Signal generation and trade simulation phases — but the causal computation pattern must be established in the VWAP phase.

---

### Pitfall 6: Price Gaps at Contract Roll Corrupt VWAP Continuity

**What goes wrong:** When switching from the expiring contract to the new front month, there's a price gap (typically 20-100+ NQ points due to contango). If VWAP calculations span across a roll boundary without adjustment, the cumulative VWAP is meaningless — it averages prices from two differently-priced contracts.

**Why it happens:** NQ futures trade in contango most of the time — the next quarter's contract trades at a premium to the expiring one. A naive continuous series spliced at the roll date has a step-function discontinuity.

**How to avoid:**
1. **Reset all VWAP calculations at the roll boundary.** Daily VWAP resets naturally (it's session-anchored), but Weekly and Monthly VWAPs that span a roll date must handle the discontinuity.
2. For Weekly/Monthly VWAP: either (a) reset at the roll and accept a partial-period VWAP, or (b) apply a Panama-canal adjustment to the old contract's prices before merging. Document which approach is used.
3. For the HTF volume profile (180-day rolling): use **ratio-adjusted** or **difference-adjusted** prices, or restrict the profile to the current contract's history only.
4. **Never mix raw prices from different contract months** in the same VWAP or volume profile calculation.

**Warning signs:** Large VWAP jumps on roll dates. Monthly VWAP values that are unreachable from current prices. Volume profile showing bimodal distributions with a 100-point gap.

**Phase to address:** Data loading phase (roll handling) and VWAP computation phase (multi-period VWAPs).

---

### Pitfall 7: Treating BBO Mid-Price as Trade Price

**What goes wrong:** When `side = N` (no trade in that 1-second interval), the code uses `(bid_px_00 + ask_px_00) / 2` as the "price" for VWAP calculation. This inflates the VWAP volume (by imputing trades that didn't happen) or, if no volume is imputed, creates gaps in the VWAP series.

**Why it happens:** The PROJECT.md notes a pending decision about using mid-price with "imputed minimal size" during low-activity periods. This is a reasonable approach for gap-filling, but the imputed volume magnitude matters enormously. If imputed volume is too high, it dilutes genuine trade-weighted VWAP. If too low, it's a no-op.

**How to avoid:**
1. **Baseline approach:** Compute VWAP from trade prints only (`side = B` or `side = A`). Ignore `side = N` rows entirely for VWAP.
2. If gaps cause numerical issues (VWAP undefined at a timestamp), forward-fill the VWAP value — the indicator simply doesn't update when no trades occur.
3. If mid-price imputation is used, set imputed volume to 1 contract (the minimum) and document the impact by comparing VWAP-with-imputation vs VWAP-without on several sessions.
4. During RTH (9:30-11:30 ET), NQ trades nearly every second — the gap problem primarily affects overnight/pre-market hours.

**Warning signs:** VWAP value at RTH open doesn't match what a trade-only calculation would show. VWAP appears "sluggish" or over-smoothed compared to charting platform references.

**Phase to address:** Data loading phase (deciding what constitutes a "trade") and VWAP computation phase.

---

## Moderate Pitfalls

### Pitfall 8: Realized Volatility Regime Classifier Has No Ground Truth

**What goes wrong:** The strategy requires classifying each session as "short gamma" or "long gamma." Without options/GEX data, the project uses realized volatility as a proxy. But the classification threshold is arbitrary — what realized vol level separates "short gamma" from "long gamma"? Poorly calibrated thresholds produce regime labels that don't match actual dealer positioning, leading to meaningless regime-segmented results.

**Why it happens:** True gamma exposure comes from options market-maker hedging flows, which aren't available in BBO data. Realized vol is a proxy, not a direct measurement. The relationship between realized vol and dealer gamma is non-linear and varies over time.

**How to avoid:**
1. Use **multiple classification approaches** and compare: (a) percentile-based (top 30% vol = short gamma), (b) absolute threshold based on historical VIX-to-realized-vol mapping, (c) intraday displacement metrics (the reference stats show short gamma produces ~32% larger displacement and 2.8x more setups).
2. **Validate the proxy** by checking that classified "short gamma" days produce the expected statistical signatures (more setups, larger displacements) versus "long gamma" days.
3. Treat regime labels as **probabilistic, not binary** — consider a three-regime model (clearly short, ambiguous, clearly long) and analyze the "ambiguous" bucket separately.
4. Accept that this is the weakest link in the backtest and flag it as a known limitation.

**Warning signs:** Regime-segmented results that show no statistical difference between regimes (suggesting the classifier is noise). Regime labels that flip daily with no persistence. Classified regime doesn't correlate with VIX levels for the same dates.

**Phase to address:** Regime classification phase — but the classification approach should be discussed during planning.

---

### Pitfall 9: Volume Profile Bin Size Distorts Structural Levels

**What goes wrong:** The HTF volume profile (180-day rolling) uses price bins that are too wide or too narrow. Too wide: multiple structural levels merge into one blob, losing the LVN/HVN resolution needed to identify "structural extremes." Too narrow: noise dominates, and every 0.25-point tick looks like a separate node.

**Why it happens:** NQ prices span a massive range (2021-2023: roughly 10,000-16,500). A fixed bin size that works at NQ 12,000 may be inappropriate at NQ 16,000. The tick size is 0.25 points, but meaningful structural levels operate at 10-50 point resolution.

**How to avoid:**
1. Use a bin size of **5-10 NQ points** for the HTF profile (20-40 ticks per bin). This balances resolution against noise.
2. For the daily profile, use **2.5-5 point bins** (10-20 ticks) for finer intra-day structure.
3. **Volume assignment method matters:** assign each trade's volume to its exact price (not distributed across a bar's range). Since the data is 1-second BBO with trade prints, assign volume to the trade price directly.
4. Validate HVN/POC locations against a charting platform for several sample days.

**Warning signs:** POC that jumps erratically with small bin size changes. LVN regions that disappear when bin size changes by 1 tick. Profile shape that looks nothing like a charting platform's profile for the same period.

**Phase to address:** Volume profile construction phase.

---

### Pitfall 10: Overfitting Entry/Exit Parameters to Historical Data

**What goes wrong:** The backtest optimizes parameters — σ entry threshold (1.7-2.2σ vs 2.2-3σ), exit target (VWAP vs POC), holding time limits, structural level proximity — to maximize in-sample performance. The "best" parameter set produces impressive results that evaporate in out-of-sample testing or live trading.

**Why it happens:** With 884 trading days and ~10+ tunable parameters, the parameter space is vast. Even a random strategy can look profitable with the right parameter combination on a fixed dataset. Research on ES/NQ VWAP strategies found that 80% of retail VWAP strategies underperform or lose money due to overfitting. However, mean reversion strategies survived rigorous Bonferroni correction testing — so the edge may be real, but parameter-specific results are not.

**How to avoid:**
1. **Test the stated model as-is** first (PROJECT.md explicitly says "testing the stated model as-is" — no optimization). Use the reference parameters (1.7-2.2σ primary zone, 2.2-3σ secondary) without modification.
2. If parameter exploration is later desired, use **walk-forward analysis**: optimize on 2021-2022, validate on 2022-2023.
3. Report results across **all parameter buckets** (1.7-2.2σ, 2.2-3σ, 3σ+), not just the best-performing one.
4. Apply a **Bonferroni correction** if testing multiple parameter combinations — divide the significance threshold by the number of tests.
5. Compare against a **null model**: randomly-timed entries of the same frequency, duration, and direction to establish baseline.

**Warning signs:** Sharpe ratio > 3.0 (suspiciously high for any single strategy). Results that are highly sensitive to small parameter changes. One parameter bucket producing all the profits.

**Phase to address:** Trade simulation and performance analysis phases.

---

### Pitfall 11: Execution Simulation Assumes Perfect Fills at Signal Price

**What goes wrong:** When the backtester detects a continuation failure at price P, it simulates entry at exactly P with zero slippage. In reality, market orders experience spread crossing and impact, and limit orders may not fill at all. At 1-second resolution, a lot happens within each bar.

**Why it happens:** Simple backtesting frameworks use "fill at close of signal bar" logic. For a 1-second bar, this seems reasonable — but NQ can move 2-5 ticks within a second during volatile periods. The bid-ask spread is typically 0.25-0.50 points (1-2 ticks) in RTH, but widens during news events.

**How to avoid:**
1. **Use the BBO data for realistic fills:** entry at `ask_px_00` for longs, `bid_px_00` for shorts (crossing the spread). This is already available in the data.
2. Add **1-tick additional slippage** as a conservative buffer for market impact.
3. Simulate entry at **T+1 bar** after signal detection at T (the signal bar's close triggers; entry is the next bar's ask/bid).
4. Run sensitivity analysis: compare results with 0, 1, 2, and 3 ticks of slippage. If the edge disappears at 2 ticks (~$10/contract round trip), the strategy is marginal.
5. Include **CME exchange fees** (~$2.32/side for NQ) in all P&L calculations.

**Warning signs:** Average win size smaller than 2 × (spread + slippage + commissions). P&L that turns negative when adding 1 tick of slippage. Fill prices that are better than the contemporary bid/ask.

**Phase to address:** Trade simulation phase.

---

### Pitfall 12: pandas Performance Collapse at Scale

**What goes wrong:** Loading 884 CSV files × ~150K rows = ~133M rows into a single pandas DataFrame. Operations like groupby, rolling calculations, and timezone conversions either consume all available RAM (a 5GB CSV dataset can balloon to 15-30GB in pandas) or take hours to complete. Row-by-row iteration (`.iterrows()`) is 237x slower than vectorized operations.

**Why it happens:** Pandas uses eager execution and creates intermediate copies during operations. String columns (like `symbol`) stored as `object` dtype consume 5-10x more memory than categorical. Default `float64` for prices wastes memory when `float32` suffices.

**How to avoid:**
1. **Pre-filter aggressively:** When loading each CSV, immediately filter to only front-month NQ rows and only the columns needed. Don't load spreads or back-month contracts.
2. **Optimize dtypes at load:** Use `dtype={'symbol': 'category', 'side': 'category'}` in `pd.read_csv()`. Cast prices to `float32` if precision allows.
3. **Process day-by-day:** Don't load all 884 files into one DataFrame. Compute daily metrics (VWAP, signals) per-file, then aggregate results.
4. **Consider Polars or DuckDB** for the data loading pipeline — Polars handles 100M+ rows in under 30 seconds for groupby operations and uses lazy evaluation to avoid intermediate copies.
5. **Pre-convert to Parquet:** Convert CSV files to Parquet once, then read from Parquet (5-10x faster loads, automatic compression, columnar access).
6. **Never use `.iterrows()` or `.apply()` with Python functions** — use vectorized numpy/pandas operations or Polars expressions.

**Warning signs:** RAM usage exceeding 8GB. Single-file processing taking >5 seconds. Full backtest taking >30 minutes. Python process killed by OS out-of-memory.

**Phase to address:** Data loading phase (architecture decision) — this must be decided early because it affects every downstream computation.

---

### Pitfall 13: `pandas.rolling().std()` Precision Bug with Outliers

**What goes wrong:** Pandas' internal rolling standard deviation algorithm uses a momentum-based approach that loses precision when data contains large outliers or operates over large value ranges. For NQ prices (10,000-16,500), the algorithm can produce incorrect σ values — documented cases show rolling std returning 57.25 when the true window std is 1.64.

**Why it happens:** This is a known pandas bug (GitHub issues #47721, #53273). The algorithm accumulates floating-point error when values are far from zero, which is exactly the case for NQ price data.

**How to avoid:**
1. Don't use `pandas.rolling().std()` for VWAP standard deviation — implement the volume-weighted expanding formula manually (see Pitfall 1).
2. If rolling std is needed for other calculations (e.g., realized vol), use `.rolling(window).agg(lambda x: np.std(x, ddof=1))` which applies numpy's std directly.
3. Alternatively, compute variance from the identity `Var(X) = E[X²] - E[X]²` using rolling sums, then take the square root.
4. Validate any rolling std output against a manual calculation on a small sample window.

**Warning signs:** NaN or negative values in standard deviation output. σ values that spike or collapse unexpectedly. Results that change when the window size changes by 1.

**Phase to address:** VWAP computation phase and regime classification phase.

---

## Minor Pitfalls

### Pitfall 14: Weekend and Holiday Data Contamination

**What goes wrong:** CSV files for Fridays may contain data past the 5:00 PM ET Globex close. Files may exist for CME holidays with partial or zero-volume sessions. Sunday evening open data may appear in Monday's file or be missing entirely.

**How to avoid:** Build a CME holiday calendar for 2021-2023. Filter data to valid Globex hours only. Flag and exclude sessions with abnormally low volume (<10% of average daily volume). Validate file count: expect ~250-252 trading days per year, not 365.

**Phase to address:** Data loading phase.

---

### Pitfall 15: `ts_recv` vs `ts_event` Timestamp Confusion

**What goes wrong:** The Databento data has two timestamps: `ts_recv` (when Databento's servers received the message) and `ts_event` (when the event occurred at CME). Using `ts_recv` for time-series ordering introduces network latency jitter; using `ts_event` is correct for market-time analysis.

**How to avoid:** Use `ts_event` for all time-based calculations (VWAP, session boundaries, signal timing). Use `ts_recv` only if analyzing latency or data pipeline timing. For the 2021-2023 data period, `ts_event` should be reliable (the pre-2017 timestamp issues don't apply).

**Phase to address:** Data loading phase.

---

### Pitfall 16: Overnight Value Area Includes Wrong Hours

**What goes wrong:** The "overnight value area" (Globex session before RTH) should capture the pre-market price distribution. But the Globex session spans from the prior day's 6:00 PM ET to 9:30 AM ET — that's 15.5 hours. If the code computes the overnight value area from midnight to 9:30, or from 6 PM to midnight, or includes the prior RTH session, the resulting value area boundaries are wrong.

**How to avoid:** Define the overnight session precisely: 6:00 PM ET (prior calendar day) to 9:29:59 AM ET (current day). Handle the day-boundary crossing explicitly. Validate that the overnight high/low matches what charting platforms show for the Globex session.

**Phase to address:** Volume profile / session analysis phase.

---

### Pitfall 17: Structural Level Detection is Ambiguous

**What goes wrong:** "Price is at a structural level" (HTF balance extreme, LVN, prior value area edge) is subjective. How close does price need to be to an LVN for it to count? Within 5 points? 10? 20? Different proximity thresholds produce dramatically different signal counts and win rates.

**How to avoid:** Define a fixed proximity threshold in points (e.g., within 10 NQ points = 40 ticks of a structural level). Test sensitivity across 5, 10, 15, 20-point thresholds and report all results. Document that this is a parameter choice, not a discovered truth.

**Phase to address:** Signal generation phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Load all data into one DataFrame | Simpler code | RAM explosion, slow processing | Only if total data fits in <4GB RAM after filtering |
| Hardcode roll dates | No volume-comparison logic needed | Breaks if data period extends; brittle | Acceptable for fixed 2021-2023 dataset if validated |
| Skip spread/slippage modeling | Faster development | Over-estimates edge by 1-3 ticks/trade | Never — NQ tick value is $5, this is material |
| Use `float64` everywhere | No precision worries | 2x memory vs `float32` | Acceptable if RAM isn't a constraint |
| Process all sessions including overnight for VWAP | Simpler session logic | VWAP reflects low-liquidity overnight noise | Only if the strategy model explicitly uses 24h VWAP |
| Single regime threshold | Simpler code | May not capture regime nuance | Early prototype only — must validate before trusting results |
| Ignore partial fill modeling | Simpler execution sim | Slight edge overestimate | Acceptable for 1-contract backtest (no market impact concern at 1 lot) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all CSVs into one DataFrame | >8GB RAM, minutes to load | Process day-by-day, pre-filter at load | Any machine with <32GB RAM |
| String `object` dtype for symbol column | Memory bloat, slow groupby | Use `category` dtype | Always — 5-10x memory savings |
| `.iterrows()` for signal detection | 10+ minutes per backtest run | Vectorize with numpy boolean masks | Any dataset >10K rows |
| Timezone conversion on full dataset | Minutes of processing | Convert at load time per-file, store as ET | >50M rows |
| Recomputing HTF volume profile daily | Hours of processing | Compute once, cache, update incrementally | 180-day window × 884 days |
| Storing intermediate results as CSV | Slow I/O, large files | Use Parquet for intermediate storage | Files >100MB |
| `pandas.rolling().std()` on large windows | Silent precision errors | Use numpy-based agg function | Windows >1000 bars with high-value data |

## "Looks Done But Isn't" Checklist

- [ ] **VWAP matches a reference platform** — Compare daily VWAP at 10:00, 11:00, 12:00 ET against TradingView/NinjaTrader for at least 5 random dates
- [ ] **σ bands are volume-weighted expanding** — Verify bands widen throughout the session (they should never contract for daily VWAP)
- [ ] **Session boundaries correct on DST dates** — Check all 6 transition dates (2021-03-14, 2021-11-07, 2022-03-13, 2022-11-06, 2023-03-12, 2023-11-05)
- [ ] **Front-month is correct at every roll** — Verify the selected contract symbol on each of the ~12 roll dates
- [ ] **No look-ahead in VWAP** — Verify VWAP(T) is identical whether computed on data[0:T] or data[0:T+1000]
- [ ] **No look-ahead in structural levels** — HTF profile levels used today were computed from data ending yesterday
- [ ] **Trade entry is T+1 from signal** — Signal at bar T, entry at bar T+1 (not bar T)
- [ ] **Fill price uses BBO, not trade price** — Longs enter at ask, shorts at bid, plus slippage
- [ ] **P&L includes commissions** — $2.32/side for NQ (~$4.64 round trip)
- [ ] **Regime classification produces expected signatures** — Short gamma days have more setups and larger displacements
- [ ] **Volume profile HVN/LVN stable across small bin changes** — Major structural levels don't move with ±1 tick bin adjustment
- [ ] **Results are comparable to reference statistics** — Win rates near 55-70%, not 85%+. If much higher, suspect look-ahead or overfitting.
- [ ] **Weekly/Monthly VWAP handle roll boundaries** — Values don't jump discontinuously on roll dates
- [ ] **Holiday sessions excluded or flagged** — CME early-close and holiday sessions produce abnormal volume

## Pitfall-to-Phase Mapping

| Pitfall | # | Prevention Phase | Verification |
|---------|---|------------------|--------------|
| Wrong VWAP σ formula | 1 | VWAP computation | Cross-validate vs charting platform |
| Wrong session anchor | 2 | VWAP computation (discuss stage) | VWAP at session start = first trade price |
| DST corrupts sessions | 3 | Data loading | Test all 6 DST transition dates |
| Roll date identification | 4 | Data loading | Verify contract symbol at each roll |
| Look-ahead bias | 5 | Signal generation + trade sim | Delayed-entry sensitivity test |
| Roll price gaps in VWAP | 6 | Data loading + VWAP computation | Weekly/Monthly VWAP continuity check |
| BBO mid-price as trade | 7 | Data loading (discuss stage) | Compare VWAP with/without imputation |
| Regime classifier | 8 | Regime classification | Validate expected statistical signatures |
| Volume profile bins | 9 | Volume profile construction | Stability test across bin sizes |
| Overfitting parameters | 10 | Performance analysis | Walk-forward validation, null model comparison |
| Perfect fill assumption | 11 | Trade simulation | Slippage sensitivity analysis (0-3 ticks) |
| pandas memory/speed | 12 | Data loading (architecture) | RAM monitoring, benchmark per-file processing time |
| Rolling std precision | 13 | VWAP computation | Manual validation on sample windows |
| Weekend/holiday data | 14 | Data loading | CME calendar validation |
| ts_recv vs ts_event | 15 | Data loading | Use ts_event for all market-time logic |
| Overnight value area hours | 16 | Volume profile / session analysis | Cross-validate session boundaries |
| Structural level proximity | 17 | Signal generation | Sensitivity analysis across thresholds |

## Sources

- CME Group: Equity Index Roll Dates — https://www.cmegroup.com/trading/equity-index/rolldates.html
- CME Group: E-mini Nasdaq-100 trading hours — https://www.cmegroup.com/trading-hours.html
- Databento: GLBX.MDP3 dataset documentation — https://databento.com/datasets/GLBX.MDP3
- Databento: Known data quality issues — https://issues.databento.com/
- pandas GitHub: Rolling std precision bug #47721, #53273
- QuantStart: Continuous Futures Contracts for Backtesting — https://www.quantstart.com/articles/Continuous-Futures-Contracts-for-Backtesting-Purposes
- EdgeTools/TradingView: VWAP strategy statistical analysis with Bonferroni correction
- Python zoneinfo DST handling: Stack Overflow verified behavior
