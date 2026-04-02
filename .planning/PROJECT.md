# VWAP Reversion Backtester

## What This Is

A backtest engine that replays ~3 years of 1-second NQ futures BBO data to test a VWAP mean reversion strategy. The system identifies when price is extended from fair value at structural extremes, mechanically defines continuation failure, and simulates reversion trades back toward value. Built for a single trader to validate and refine the baytrading VWAP reversion model with hard data.

## Core Value

Accurately measure the statistical edge of entering NQ reversion trades when price is extended from VWAP at structural levels during the first 1-2 hours of the NY session — across different volatility regimes.

## Requirements

### Validated

- Phase 1 (2026-04-02): CME Globex BBO ingestion, causal front-month mapping, ET session labeling, partitioned parquet cache, and audit artifact generation are in place for NQ-only data.

### Active

- [ ] Load and parse CME Globex MDP3 BBO 1-second CSV data (one file per day)
- [ ] Identify and filter to front-month NQ contract (handle quarterly rolls)
- [ ] Compute Daily VWAP from trade prints (price × size weighting)
- [ ] Compute Weekly VWAP (rolling across sessions within the week)
- [ ] Compute Monthly VWAP (rolling across sessions within the month)
- [ ] Compute VWAP standard deviation bands in real-time (1σ through 4σ)
- [ ] Build daily volume profiles from trade prints (price × volume histogram)
- [ ] Build HTF volume profiles (rolling 180-day window) to identify balance areas and LVNs
- [ ] Compute overnight value area (globex session before RTH)
- [ ] Classify each session's gamma regime (short vs long) from realized volatility
- [ ] Filter trading window to first 1-2 hours after RTH open (9:30-11:30 ET)
- [ ] Detect when price is meaningfully extended from VWAP (1.7σ to 3σ range)
- [ ] Detect when extended price is at a structural level (HTF balance extreme, LVN, prior value area edge)
- [ ] Define mechanical continuation failure from price action (rejection pattern at level)
- [ ] Simulate trade entry after failure confirmation
- [ ] Target reversion to Daily VWAP, Weekly VWAP, or developing POC
- [ ] Track trade-level results (entry, exit, P&L, duration, sigma at entry, regime)
- [ ] Compute backtest performance metrics (win rate, avg win/loss, profit factor, max drawdown, Sharpe)
- [ ] Break down results by gamma regime (short vs long)
- [ ] Break down results by deviation band (1.7-2.2σ, 2.2-3σ, 3σ+)
- [ ] Output results to structured format (CSV/JSON) for analysis

### Out of Scope

- Live execution / order routing — this is backtest only
- Orderflow confirmation (DOM/tape) — not available in BBO data
- ES or other instruments — NQ front month only
- Options/GEX data integration — gamma regime derived from realized vol
- GUI / dashboard — command-line backtest with file output
- Machine learning / optimization — deferred to v2 milestone (feature engineering, classification models, RL optimization, walk-forward testing)

## Context

**Data source:** CME Globex (GLBX) MDP3 BBO 1-second snapshots, sourced via Databento. ~884 daily CSV files covering Feb 2021 through Nov 2023. Each file contains all NQ contract months and spreads; front-month filtering required.

**Data fields:** `ts_recv`, `ts_event`, `rtype`, `publisher_id`, `instrument_id`, `side`, `price`, `size`, `flags`, `sequence`, `bid_px_00`, `ask_px_00`, `bid_sz_00`, `ask_sz_00`, `bid_ct_00`, `ask_ct_00`, `symbol`

**Key data behaviors:**
- `side` = B or A indicates a trade occurred (price/size populated)
- `side` = N means no trade in that interval (BBO snapshot only)
- Multiple symbols per file (NQH1, NQM1, NQU1, NQZ1, spreads)
- Contract symbols follow CME naming: NQ + month code (H/M/U/Z) + year digit
- Files are ~15-22MB each, ~150K rows per day across all symbols

**Data location:** `C:\Users\pranav\Desktop\trading\vector\GLBX-20260328-8QJU3AUJ9E\csv\`

**Strategy reference statistics (from model author):**
- Median max deviation before return: ~2.0σ
- 75th percentile: ~2.6σ, 90th percentile: ~3.0σ
- Return probability: 1.0-1.5σ → ~96%, 1.5-2.0σ → ~93-95%, 2.0-2.5σ → ~88-92%
- Highest probability zone: 1.7σ to 2.2σ
- Short gamma: ~2.8x more setups, ~32% larger displacement (avg 46.9 ticks vs 35.6)
- Mechanical results (no orderflow): ~55-60% immediate rejection, up to ~70% full VWAP return at key levels

**NQ contract specs:** Tick size = 0.25 points, tick value = $5.00, point value = $20.00

## Constraints

- **Language**: Python — standard data science ecosystem (pandas, numpy)
- **Data format**: CSV files, one per trading day, read from local disk
- **Performance**: Must handle ~884 files × ~150K rows each efficiently; consider chunked processing or pre-filtering
- **Time zones**: All timestamps in UTC; must convert to US/Eastern for session logic (RTH open 9:30 AM ET)
- **Contract rolls**: NQ rolls quarterly (March, June, September, December) — typically the Thursday before expiration Friday

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| NQ front month only | Matches the live trading model; highest liquidity | — Pending |
| Gamma from realized vol | No options/GEX data available; vol regime is a reasonable proxy | — Pending |
| Mechanical failure definition | No DOM/tape data; price-action-based rejection serves as proxy for failed continuation | — Pending |
| Mid-price for VWAP when no trades | During low-activity periods, use mid-price with imputed minimal size to avoid gaps | — Pending |
| Python | Standard ecosystem for data analysis; user is building a research tool, not a production system | Polars-first package with parquet cache CLI shipped in Phase 1 |
| Phase 1 canonical timestamp | `ts_event` may be blank on quote-only rows | Use parsed `ts_recv` as the structural ordering key and preserve `ts_event` when present |
| Phase 1 cache layout | Downstream phases need one trusted dataset | Use one canonical parquet dataset partitioned by `trading_date` with sibling roll/quality/schema artifacts |

## Current State

Phase 1 is complete. The codebase now has a runnable `src/` package, typed Databento ingestion, same-day volume front-month selection, ET session/trading-date labels, a partitioned canonical parquet cache, and a Phase 1 CLI build command that emits benchmark and audit artifacts.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-02 after Phase 1 completion*
