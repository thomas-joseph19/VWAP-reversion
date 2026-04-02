# Project Research Summary

**Project:** VWAP Reversion Backtester
**Domain:** NQ Futures VWAP Reversion Backtesting
**Researched:** 2026-04-01
**Confidence:** HIGH

## Executive Summary

This is a single-strategy, single-instrument backtest research tool — not a trading platform. The research is unanimous: build from composable libraries (Polars, NumPy, Numba), not a backtesting framework. No existing framework (Backtrader, VectorBT, NautilusTrader) can express the strategy's custom computations — rolling multi-timeframe VWAP with volume-weighted expanding σ bands, HTF composite volume profiles, structural level confluence detection, and mechanical continuation-failure identification from BBO data. The framework overhead (portfolio management, multi-asset routing, live trading hooks) is dead weight for a single-contract replay-style backtest. A six-stage vectorized pipeline is the right architecture: ingest → session structure → indicators → setup detection → trade simulation → analytics. Only the trade simulator requires sequential processing; everything else is DataFrame transforms on ~50-70M rows of front-month NQ data.

The recommended approach starts by answering one binary question: "Does entering at 1.7σ+ from VWAP, at structural levels, during the first 1-2 hours of RTH, produce positive-expectancy reversion trades?" A lean MVP (data pipeline + daily VWAP + σ bands + simple structural levels + trade sim with slippage) can answer this across 884 sessions in under 4 minutes per run. Only after confirming the edge exists should the system be extended with HTF volume profiles, regime classification, multi-timeframe VWAPs, and advanced analytics that decompose the edge by regime, σ-band, and time-of-day.

The critical risks are computational correctness, not performance. VWAP standard deviation uses an unusual volume-weighted expanding formula that most developers implement wrong. DST transitions corrupt session boundaries twice a year across six transitions in the data. Front-month identification breaks at quarterly roll dates if not handled with volume-based detection. Look-ahead bias silently inflates results if volume profile levels or VWAP values are computed from future data. All of these are preventable with explicit validation steps, but they must be addressed in the foundational phases — mistakes here propagate silently through every downstream result.

## Key Findings

### Recommended Stack

Custom build on Python 3.13 with composable numeric libraries. No backtesting framework. The stack is minimal and conflict-free.

**Core technologies:**
- **Polars ≥1.39.1:** Data loading, filtering, aggregation — 5-30x faster than Pandas at this scale, lazy evaluation filters front-month contracts before loading into memory
- **NumPy ≥2.4.4:** VWAP cumsum, σ bands, volume profile histograms — the lingua franca between Polars output and Numba
- **Numba ≥0.65.0:** JIT compilation for the trade simulation event loop — 10-50x speedup over pure Python for non-vectorizable per-bar logic
- **PyArrow ≥23.0.1:** CSV→Parquet one-time conversion for 5-10x faster subsequent loads
- **zoneinfo + tzdata:** Stdlib timezone handling (replaces pytz); tzdata required on Windows

**Explicitly excluded:** Pandas as primary engine (too slow at 100M+ rows), ta-lib (VWAP is 5 lines of NumPy), Backtrader (abandoned, slow), pytz (legacy DST bugs), databases (no random-access queries needed), Matplotlib (out of scope).

**Expected performance:** ~2-5 min one-time CSV→Parquet conversion, then 1-4 minutes per full backtest run. Peak memory ~3-5GB.

### Expected Features

**Must have (v1 — "Does the edge exist?"):**
- CSV data ingestion with front-month NQ detection and quarterly roll handling
- UTC → Eastern timezone conversion with DST-correct session boundaries
- Daily VWAP + volume-weighted expanding σ bands (1σ through 4σ)
- RTH trading window filter (9:30-11:30 ET)
- Deviation extension detection (1.7σ to 3σ)
- Simple structural levels (prior day's VAH/VAL/POC as proxy)
- Trade simulation with slippage + commission modeling
- Trade-level result tracking with core performance metrics
- Structured CSV/JSON output

**Should have (v1.x — "How does the edge vary?"):**
- Weekly and Monthly VWAP as additional reversion targets
- Daily + HTF (180-day rolling) volume profiles with POC/VAH/VAL/LVN
- Full structural level detection (HTF balance extremes, LVNs, overnight VA edges)
- Volatility regime classification (short/long gamma from realized vol)
- Mechanical continuation failure definition from price action
- Regime-segmented and σ-band-segmented analytics
- Multi-target exit logic, session context tracking, time-of-day analytics

**Defer (v2+):**
- Out-of-sample validation framework
- Parameter sensitivity analysis
- Equity curve analysis
- Trade visualization export

**Anti-features (never build):** Parameter optimizer/grid search, ML-based signals, GUI/dashboard, live execution, multi-instrument support, order book simulation, walk-forward optimization.

### Architecture Approach

Six-stage vectorized pipeline where each stage transforms a DataFrame and passes it downstream. Not event-driven — the strategy rules are fully mechanical, BBO data can't support realistic fill simulation, and vectorized operations are 10-100x faster for 50M+ rows. The single exception is trade simulation (Stage 5), which walks a small setup DataFrame (~500-2K rows) chronologically to track position state.

**Major components:**
1. **Data Pipeline** (`data/`) — CSV loading with dtype optimization, front-month contract resolution, UTC→ET session boundary detection
2. **Indicator Engine** (`indicators/`) — Daily/Weekly/Monthly VWAP with σ bands, daily + HTF volume profiles, regime classifier — all stateless DataFrame transforms except the rolling 180-day profile store
3. **Strategy Logic** (`strategy/`) — Setup scanner (time + σ + structural confluence), continuation failure detector, trade simulator with position tracking
4. **Analytics** (`analytics/`) — Performance metrics, regime/σ-band/time breakdowns, CSV/JSON export
5. **Config** (`config.py`) — Single source of truth for all parameters; no magic numbers in strategy logic
6. **Pipeline Orchestrator** (`pipeline.py`) — Wires stages together; the only module that imports from all packages

**Key patterns:** DataFrame-in/DataFrame-out stages, centralized configuration dataclass, explicit session boundaries computed once and reused, volume profiles stored as lookup structures keyed by date.

### Critical Pitfalls

1. **VWAP σ formula is non-standard** — Must use volume-weighted expanding stddev (`sqrt(Σ(v×p²)/Σ(v) - VWAP²)`), not `rolling().std()`. Validate against TradingView/NinjaTrader on 5+ sessions.
2. **DST transitions corrupt session boundaries** — Six transitions in the 2021-2023 data shift RTH open by 1 hour in UTC. Use `zoneinfo` (not pytz), convert once at load time, never hardcode UTC offsets. Test all 6 DST dates explicitly.
3. **Front-month identification breaks at rolls** — Use volume-based roll rule (highest daily volume wins) or hardcoded CME roll date table. Verify contract symbol at all ~12 quarterly rolls.
4. **Look-ahead bias in indicators** — VWAP must be strictly cumulative/causal. Structural levels must use prior completed sessions only, never developing session data. Entry at T+1 after signal at T.
5. **Perfect fill assumption overestimates edge** — Use BBO data for fills (ask for longs, bid for shorts) plus 1-tick slippage plus CME commissions ($2.32/side). Run sensitivity at 0-3 ticks slippage.

## Implications for Roadmap

Based on combined research, the build order is dictated by strict data dependencies. Each phase produces an artifact consumed by subsequent phases.

### Phase 1: Data Pipeline Foundation
**Rationale:** Everything downstream needs clean, session-structured, front-month NQ data. This is the foundation — get it wrong and every indicator, signal, and trade result is corrupted.
**Delivers:** Parquet-cached, front-month-filtered, session-labeled timeseries with correct timezone handling
**Addresses:** CSV ingestion, front-month detection, roll handling, timezone conversion, session boundaries, Parquet cache
**Avoids:** Pitfalls 3 (DST), 4 (roll dates), 6 (roll price gaps), 7 (BBO mid-price), 14 (holidays), 15 (ts_recv vs ts_event)

### Phase 2: VWAP Engine
**Rationale:** The core indicator of the entire strategy. Daily VWAP + σ bands define what "extended from fair value" means. Must be validated against a reference platform before any signal logic is built.
**Delivers:** Daily VWAP + σ bands (1σ-4σ) as columns on the main DataFrame
**Addresses:** Daily VWAP computation, σ band calculation, mid-price handling for no-trade intervals
**Avoids:** Pitfalls 1 (wrong σ formula), 2 (wrong session anchor), 5 (look-ahead in VWAP), 13 (rolling std precision bug)

### Phase 3: MVP Trade Simulation
**Rationale:** Completes the v1 system that answers the binary research question. Uses simple structural levels (prior day's VA) as a proxy — avoids the high-complexity volume profile engine for the initial answer.
**Delivers:** End-to-end backtest producing trade log + performance metrics across 884 sessions
**Addresses:** RTH window filter, deviation detection, simple structural levels, trade simulator, slippage/commissions, trade logging, core metrics, CSV/JSON output
**Avoids:** Pitfalls 5 (look-ahead), 10 (overfitting — tests stated parameters only), 11 (fill assumptions)

### Phase 4: Volume Profile Engine
**Rationale:** Highest-complexity feature set. Daily profiles are per-session and relatively straightforward. The 180-day HTF rolling profile is the expensive part — implemented as incremental daily histogram summation, not re-binning. Overnight value area enables richer structural context.
**Delivers:** Daily + HTF volume profiles with POC/VAH/VAL/LVN, overnight value area
**Addresses:** Daily volume profiles, HTF 180-day rolling profiles, balance area detection, LVN detection, overnight value area
**Avoids:** Pitfalls 9 (bin size distortion), 16 (overnight VA hours)

### Phase 5: Regime Classification + Multi-timeframe VWAP
**Rationale:** These indicators are independent of volume profiles and can be built in parallel conceptually, but sequenced here for simplicity. Regime classification is the weakest link (no ground truth for gamma) — needs multiple classification approaches and validation against expected statistical signatures.
**Delivers:** Weekly/Monthly VWAP columns + per-session regime labels (short/long gamma)
**Addresses:** Weekly VWAP, Monthly VWAP, realized volatility regime classification
**Avoids:** Pitfalls 6 (roll gaps in multi-period VWAP), 8 (regime classifier without ground truth)

### Phase 6: Full Strategy + Advanced Analytics
**Rationale:** Now all indicators exist. Build the complete strategy logic: full structural level detection combining HTF profiles + LVNs + overnight VA edges, mechanical continuation failure from price action, multi-target exit logic. Then decompose results by every available dimension.
**Delivers:** Complete v1.x system with full structural confluence, failure detection, regime/σ/time analytics
**Addresses:** Full structural level detection, continuation failure, multi-target exits, regime-segmented analytics, σ-band analytics, session context, time-of-day analytics
**Avoids:** Pitfalls 17 (structural level ambiguity — requires sensitivity testing across proximity thresholds)

### Phase Ordering Rationale

- **Phases 1→2→3 form the critical path to the MVP.** The research question ("does the edge exist?") can be answered with just these three phases. If the aggregate signal is negative-expectancy, Phases 4-6 are deprioritized.
- **Phase 4 is deferred despite being strategy-critical** because volume profiles are the highest-complexity feature (FEATURES.md) and prior-day VA serves as an adequate structural proxy for the MVP.
- **Phase 5 groups two independent indicators** (multi-TF VWAP and regime) that share a common characteristic: they span multiple sessions and must handle contract roll boundaries.
- **Phase 6 integrates everything** — it can only be built after all indicators (Phases 2, 4, 5) exist. This is where the continuation failure definition gets iterated, which the research flags as the hardest feature to get right from BBO data.

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 1 (Data Pipeline):** Front-month roll detection logic needs investigation — volume-based vs hardcoded roll dates, handling of the multi-day volume migration period
- **Phase 4 (Volume Profile):** HTF profile rolling window implementation, LVN detection algorithm, bin size calibration across the NQ price range (10,000-16,500)
- **Phase 6 (Full Strategy):** Mechanical continuation failure definition from BBO data — the model author uses DOM/tape which isn't available; the price-action proxy needs iterative refinement

**Phases with standard patterns (skip research-phase):**
- **Phase 2 (VWAP Engine):** Well-documented formula, just needs correct implementation of the volume-weighted expanding variant
- **Phase 3 (MVP Trade Sim):** Standard backtest simulation; the complexity is in getting indicators right, not the trade logic
- **Phase 5 (Regime + Multi-TF VWAP):** Straightforward extensions of Phase 2 VWAP + standard realized vol computation

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Polars/NumPy/Numba is a well-validated stack for numeric Python at this data scale. No exotic dependencies. |
| Features | HIGH | Feature list derives directly from the strategy model description in PROJECT.md. MVP/v1.x/v2+ split is clean. |
| Architecture | HIGH | Vectorized pipeline is the established pattern for mechanical backtests on historical data. Build order follows strict data dependencies. |
| Pitfalls | HIGH | Core pitfalls (VWAP formula, DST, roll dates, look-ahead) are well-documented in quantitative finance. Pandas precision bugs are verified via GitHub issues. |

**Overall confidence:** HIGH — the domain is well-understood, the strategy is fully specified, and the data format is documented. The unknowns are implementation-specific (continuation failure definition, regime threshold calibration), not architectural.

### Gaps to Address

- **Continuation failure definition:** The model author identifies trade entry via DOM/tape confirmation, which BBO data cannot provide. The price-action proxy (failed new high/low, reversal bar) needs a precise mechanical definition — expect iterative refinement during Phase 6 planning/execution.
- **Regime classification threshold:** No ground truth for gamma exposure from BBO data alone. Must test multiple classification approaches (percentile-based, absolute threshold, displacement-based) and validate against expected statistical signatures (2.8x more setups in short gamma). Accept this as the weakest link and flag it in results.
- **VWAP anchor convention for overnight data:** PROJECT.md has a pending decision on whether daily VWAP includes overnight volume or RTH-only. This must be resolved before Phase 2 implementation — it changes the VWAP value at RTH open.
- **Weekly/Monthly VWAP across contract rolls:** When a quarterly roll occurs mid-week or mid-month, the multi-period VWAP either resets (losing context) or needs price adjustment. The approach must be decided during Phase 5 planning.

## Sources

### Primary (HIGH confidence)
- CME Group: Equity Index Roll Dates, trading hours, NQ contract specs
- Databento: GLBX.MDP3 dataset documentation, data field semantics
- Python stdlib: zoneinfo/tzdata DST handling documentation
- Polars v1.39.1, NumPy v2.4.4, Numba v0.65.0, PyArrow v23.0.1 release documentation
- pandas GitHub: Rolling std precision bugs #47721, #53273

### Secondary (MEDIUM confidence)
- Polars vs Pandas benchmarks at 100M+ row scale (community benchmarks, multiple sources agree)
- VectorBT vs event-driven backtesting comparisons (Python.financial, community consensus)
- VWAP standard deviation formula implementations (TradingView, NinjaTrader indicator docs)
- Backtesting anti-patterns and overfitting research (QuantifiedStrategies, PickMyTrade, EdgeTools)
- QuantStart continuous futures methodology papers

### Tertiary (LOW confidence)
- Regime classification from realized vol as gamma proxy — no direct validation source; effectiveness depends on correlation between realized vol and dealer gamma positioning, which varies over time
- Mechanical continuation failure from BBO data — no established methodology; this is novel and approximate by nature

---
*Research completed: 2026-04-01*
*Ready for roadmap: yes*
