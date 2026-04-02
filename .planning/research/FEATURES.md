# Feature Research

**Domain:** NQ Futures VWAP Reversion Backtesting
**Researched:** 2026-04-01
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Must Have for Reliable Backtest)

Without these, the backtest produces unreliable or misleading results.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **CSV data ingestion** | Must load ~884 daily BBO files from disk efficiently | Low | Read CSV with pandas, filter columns, parse timestamps |
| **Front-month contract detection** | Mixed symbols per file; wrong contract = wrong data | Medium | Parse CME symbol codes (NQ + H/M/U/Z + year), select highest-OI quarterly, handle roll dates |
| **Quarterly contract roll handling** | NQ rolls quarterly; naive splicing creates false signals at roll boundaries | Medium | Detect roll Thursday before expiration Friday; no price adjustment needed since VWAP resets daily |
| **UTC → Eastern timezone conversion** | Session logic (RTH open, globex/overnight) requires ET; raw data is UTC | Low | Use `pytz` or `zoneinfo`; handle DST transitions correctly |
| **Session boundary detection** | RTH (9:30-16:15 ET) vs globex session must be classified correctly | Low | Tag each row as RTH or globex based on ET timestamp |
| **Daily VWAP computation** | Core anchor of the strategy — everything references deviation from VWAP | Medium | Cumulative (price × size) / cumulative size from RTH open; reset daily; handle zero-trade intervals |
| **VWAP standard deviation bands** | Entry signals fire at σ thresholds (1.7σ–3σ); must be computed in real-time | Medium | Running population stddev of price vs VWAP, weighted by volume; bands at 1σ through 4σ |
| **Trade simulation engine** | Must simulate entry, hold, and exit with defined rules — not just signal detection | Medium | State machine: idle → signal → entry → manage → exit; track position, entry price, P&L |
| **Slippage and commission modeling** | Without friction costs, results are fantasy; NQ has tight spreads but slippage matters | Low | Configurable fixed slippage (e.g., 1 tick per side) + per-contract commission |
| **Trade-level result tracking** | Must record every trade with full context for post-hoc analysis | Low | Log: entry time/price, exit time/price, P&L, duration, σ at entry, regime, structural level |
| **Core performance metrics** | Win rate, avg win/loss, profit factor, max drawdown, Sharpe — the minimum for evaluating any strategy | Medium | Compute from trade log; need at least 30-50 trades per segment for statistical reliability |
| **Structured output** | Results must be exportable for analysis in notebooks/Excel | Low | CSV and/or JSON output of trade log + summary statistics |
| **Mid-price for BBO-only intervals** | When `side=N` (no trade), VWAP computation needs a price reference | Low | Use (bid_px + ask_px) / 2 with imputed minimal size; prevents VWAP gaps during quiet periods |
| **Deterministic replay** | Same data + same params = same results every time | Low | No randomness in core simulation; pseudo-random only if Monte Carlo added later |

### Differentiators (Strategy-Specific Edge)

These features are what make this engine specifically useful for the VWAP reversion model, rather than being a generic backtester.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Weekly VWAP** | Reversion targets include weekly VWAP; weekly context changes trade expectation | Medium | Rolling cumulative across sessions within calendar week; reset Monday globex open |
| **Monthly VWAP** | Monthly VWAP as reversion target and context for how extended price is on higher timeframe | Medium | Rolling cumulative across sessions within calendar month; reset first session of month |
| **Daily volume profile** | Identifies developing POC, value area — potential reversion targets and structural context | High | Price × volume histogram with configurable tick granularity; compute VAH/VAL/POC in real-time |
| **HTF volume profile (180-day rolling)** | Identifies balance areas and LVNs that serve as structural support/resistance for entry confluence | High | Composite profile across ~180 sessions; must incrementally add/remove days for efficiency |
| **Overnight value area** | Globex session value area provides structural context for RTH open dynamics | Medium | Compute VAH/VAL/POC from midnight to 9:30 ET data only |
| **Structural level detection** | The strategy requires confluence of σ extension + structural level; this automates "is price at a level?" | High | Match current price against HTF balance extremes, LVNs, prior day VAH/VAL, overnight VA edges |
| **Volatility regime classification** | Short gamma vs long gamma regimes produce fundamentally different trade characteristics (~2.8× more setups in short gamma) | Medium | Realized vol over N-day window; classify based on percentile ranking or threshold; no options data needed |
| **RTH trading window filter** | Strategy only trades first 1-2 hours; filtering eliminates noise from irrelevant periods | Low | Boolean mask: 9:30-11:30 ET; configurable start/end times |
| **Mechanical continuation failure** | Defines entry trigger without DOM/tape — price-action-based rejection at structural level | High | Must define rejection pattern (e.g., failed new high/low, reversal bar) from 1-second BBO data |
| **Multi-target exit logic** | Reversion targets differ (daily VWAP, weekly VWAP, developing POC); must test each | Medium | Configurable target selection; track which target hit first; partial exit support optional |
| **Regime-segmented analytics** | Break down results by short/long gamma — the strategy's core hypothesis is regime-dependent edge | Medium | Group trade log by regime classification; compute all metrics per group independently |
| **Deviation-band-segmented analytics** | Break down by entry σ level (1.7-2.2σ, 2.2-3σ, 3σ+) — validates the probability distribution claim | Low | Group trade log by σ at entry; bucket into configurable ranges |
| **Session-level context tracking** | Track session characteristics (opening gap, overnight range, initial balance) that may correlate with setup quality | Medium | Compute per-session: gap size, ON range, IB high/low/range; attach to each trade for analysis |
| **Time-of-day analytics** | Break down results by entry time within RTH window — reveals if edge concentrates in specific minutes | Low | Group trade log by entry time bucket (e.g., 15-min bins within 9:30-11:30) |

### Anti-Features (Avoid Building)

These are features that seem useful but would actively harm the project's goals, add unjustified complexity, or lead to unreliable conclusions.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Parameter optimizer / grid search** | "Find the best σ threshold" | Guarantees overfitting with ~884 sessions; the strategy has stated parameters from the model author — the point is testing THOSE parameters, not finding new ones | Test the stated parameters (1.7σ–2.2σ, 2.2σ–3σ); use out-of-sample validation if comparing a small set |
| **ML-based signal generation** | "Let the model find patterns" | Contradicts the goal — we're testing a specific discretionary model mechanically, not discovering new models; ML on 884 sessions will overfit | Stick to the defined rules; ML is a different project entirely |
| **Continuous contract price adjustment** | "Panama canal / ratio-adjusted prices" | VWAP resets daily, so roll gaps don't affect VWAP computation; adjusted prices would distort the σ calculations that drive entries | Use raw unadjusted prices; skip the roll day itself if needed |
| **GUI / real-time dashboard** | "Visualize signals as they develop" | PROJECT.md explicitly scopes this as CLI + file output; a GUI is a separate project that delays the core research question | Output CSV/JSON; use Jupyter notebooks for ad-hoc visualization |
| **Live execution / order routing** | "Go live with winning strategy" | Out of scope per PROJECT.md; mixing execution concerns with backtest logic creates complexity with no research value | Keep backtest pure; build execution separately if results warrant |
| **Multi-instrument support** | "Test on ES, YM, RTY too" | PROJECT.md scopes to NQ only; generalizing data parsing, contract specs, and session logic adds complexity for zero current value | Hardcode NQ specs; if needed later, refactor is cheap |
| **Order book / DOM simulation** | "Simulate realistic fills with depth" | BBO data only has top-of-book; simulating depth from BBO is fantasy data; the strategy explicitly acknowledges no orderflow confirmation | Use simple fill model: trade at signal price + slippage |
| **Tick-by-tick event-driven engine** | "Process every market update as event" | 1-second bars are already aggregated; event-driven overhead is unnecessary for bar-based replay; vectorized approach is 10-100× faster for this data | Vectorized replay through pandas/numpy; state machine for trade simulation only |
| **Walk-forward optimization** | "Re-optimize parameters over time" | No parameters to optimize — we're testing fixed rules; walk-forward is for adaptive systems, not model validation | Split data into in-sample / out-of-sample halves for validation |
| **Monte Carlo position sizing** | "Optimal position size via simulation" | Single-contract backtest; position sizing is irrelevant until the edge is proven to exist | Report per-contract P&L; sizing is a downstream decision |
| **Intraday margin / liquidation modeling** | "Track margin requirements tick by tick" | Single-contract backtest with defined stops; margin isn't a constraint at this scale; adds complexity for no insight | Track max adverse excursion (MAE) per trade instead |

## Feature Dependencies

```
CSV Data Ingestion
├── Front-month Contract Detection
│   └── Quarterly Contract Roll Handling
├── UTC → Eastern Timezone Conversion
│   └── Session Boundary Detection
│       ├── RTH Trading Window Filter
│       └── Overnight Value Area
└── Mid-price for BBO-only Intervals

Daily VWAP Computation (requires: data ingestion, session boundaries, mid-price handling)
├── VWAP Standard Deviation Bands
│   └── Deviation Extension Detection (1.7σ–3σ)
│       └── Setup Identification (requires: structural levels + deviation)
│           └── Mechanical Continuation Failure
│               └── Trade Simulation Engine
│                   ├── Slippage & Commission Modeling
│                   ├── Multi-target Exit Logic
│                   └── Trade-level Result Tracking
│                       ├── Core Performance Metrics
│                       ├── Regime-segmented Analytics
│                       ├── Deviation-band-segmented Analytics
│                       ├── Time-of-day Analytics
│                       └── Structured Output (CSV/JSON)
├── Weekly VWAP (requires: cross-session state)
└── Monthly VWAP (requires: cross-session state)

Daily Volume Profile (requires: data ingestion, session boundaries)
├── Developing POC / Value Area
└── HTF Volume Profile - 180-day Rolling
    ├── Balance Area Detection
    └── LVN Detection
        └── Structural Level Detection (combines: HTF profile + daily VA + overnight VA)

Volatility Regime Classification (requires: multi-session realized vol)
└── Regime-segmented Analytics (requires: trade log)

Session-level Context Tracking (requires: session boundaries, data ingestion)
```

## MVP Definition

### Launch With (v1) — "Does the edge exist?"

The minimum to answer: "Does entering at 1.7σ+ from VWAP, at structural levels, during the first 1-2 hours of RTH, produce a positive-expectancy reversion trade?"

1. CSV data ingestion + front-month detection + contract roll handling
2. Timezone conversion + session boundary detection
3. Daily VWAP + standard deviation bands
4. RTH trading window filter (9:30-11:30 ET)
5. Deviation extension detection (price at 1.7σ+)
6. Simple structural level check (prior day's VAH/VAL/POC as initial proxy)
7. Basic trade simulation (entry after extension, target VWAP, fixed stop)
8. Slippage + commission modeling
9. Trade-level result tracking
10. Core performance metrics (win rate, profit factor, Sharpe, max drawdown)
11. Structured CSV output

### Add After Validation (v1.x) — "How does the edge vary?"

Once v1 confirms a positive-expectancy signal exists, add features that decompose and refine it:

1. Weekly and Monthly VWAP (additional reversion targets)
2. Daily volume profile with developing POC
3. HTF volume profile (180-day rolling) with balance areas and LVNs
4. Full structural level detection (HTF balance extremes, LVNs, overnight VA edges)
5. Volatility regime classification (short/long gamma)
6. Mechanical continuation failure definition
7. Overnight value area computation
8. Regime-segmented analytics
9. Deviation-band-segmented analytics
10. Multi-target exit logic
11. Session-level context tracking
12. Time-of-day analytics

### Future Consideration (v2+) — "Refine and stress-test"

Only after the model is validated and decomposed:

1. Out-of-sample validation framework (split data temporally)
2. Parameter sensitivity analysis (vary σ thresholds ±0.2 to check robustness, NOT optimize)
3. Equity curve analysis (drawdown duration, recovery periods, regime transitions)
4. Trade visualization export (generate chart-ready data for specific trades)
5. Overnight session extension detection (does the pattern work before RTH?)

## Feature Prioritization Matrix

| Feature | User Value | Impl. Cost | Priority | Phase |
|---------|-----------|------------|----------|-------|
| CSV data ingestion + front-month detection | Critical | Low-Med | **P0** | v1 |
| Timezone + session boundaries | Critical | Low | **P0** | v1 |
| Daily VWAP + σ bands | Critical | Medium | **P0** | v1 |
| RTH window filter | High | Low | **P0** | v1 |
| Deviation detection | Critical | Low | **P0** | v1 |
| Simple structural levels (prior day VA) | High | Medium | **P0** | v1 |
| Trade simulation engine | Critical | Medium | **P0** | v1 |
| Slippage + commissions | High | Low | **P0** | v1 |
| Trade logging + core metrics | Critical | Medium | **P0** | v1 |
| Structured output | High | Low | **P0** | v1 |
| Weekly/Monthly VWAP | High | Medium | **P1** | v1.x |
| Daily volume profile + POC | High | High | **P1** | v1.x |
| HTF volume profile + LVNs | High | High | **P1** | v1.x |
| Full structural level detection | High | High | **P1** | v1.x |
| Volatility regime classification | High | Medium | **P1** | v1.x |
| Continuation failure definition | High | High | **P1** | v1.x |
| Overnight value area | Medium | Medium | **P1** | v1.x |
| Regime-segmented analytics | High | Medium | **P1** | v1.x |
| Deviation-band analytics | Medium | Low | **P1** | v1.x |
| Multi-target exits | Medium | Medium | **P1** | v1.x |
| Session context tracking | Medium | Medium | **P1** | v1.x |
| Time-of-day analytics | Low-Med | Low | **P1** | v1.x |
| Out-of-sample validation | Medium | Medium | **P2** | v2+ |
| Parameter sensitivity | Medium | Medium | **P2** | v2+ |
| Equity curve analysis | Low-Med | Medium | **P2** | v2+ |
| Trade visualization export | Low | Low | **P2** | v2+ |

## Key Observations

**The core research question is binary:** Does entering at σ extension + structural level + time filter produce positive expectancy when targeting VWAP reversion? V1 answers this with minimal features. Everything else decomposes and refines.

**Volume profiles are the highest-complexity feature** and the most likely to consume implementation time disproportionate to initial value. Use prior-day VAH/VAL/POC as a structural proxy in v1; full HTF composite profiles are v1.x.

**Regime classification is strategy-critical but not v1-critical.** The model author reports 2.8× more setups in short gamma — if the overall signal is negative-expectancy, regime segmentation won't save it. Test the aggregate first, then decompose by regime.

**Mechanical continuation failure is the hardest feature to define well.** The model author uses DOM/tape for this in live trading, which isn't available in BBO data. The price-action proxy (failed new high/low, reversal bar patterns) needs careful definition and is inherently approximate. This is the feature most likely to need iterative refinement.

## Sources

- CME Globex trading hours and session boundaries: CME Reference Data API documentation
- VWAP standard deviation band calculation methodology: TradingView indicator implementations, GitHub reference implementations
- Volume profile features (LVN detection, balance areas): NinjaTrader and TradingView indicator documentation
- Backtesting anti-patterns and overfitting risks: QuantifiedStrategies.com, PickMyTrade blog (2026)
- Continuous futures contract handling: QuantPedia, QuantStart methodology papers
- Backtesting metrics standards: Backtrex documentation, Freqtrade documentation
- Python backtesting landscape: VectorBT documentation, python.financial framework comparison (2026)
- Volatility regime classification approaches: GitHub volatility-trading framework, adaptive execution frameworks
