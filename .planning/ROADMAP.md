# Roadmap: VWAP Reversion Backtester

## Overview

Build a Python backtesting engine that replays ~884 days of 1-second NQ futures BBO data to measure the statistical edge of VWAP mean reversion trades at structural levels. Phases 1-6 form the MVP critical path — answering "does the edge exist?" with simple structural proxies. Phases 7-10 extend the system with full volume profiles, regime classification, multi-timeframe VWAPs, and advanced analytics to characterize how the edge varies across conditions. The build order follows strict data dependencies: clean data → indicators → signals → trades → analytics.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Pipeline Foundation** - Ingest, filter, and structure CME BBO data into clean front-month NQ timeseries with session boundaries
- [ ] **Phase 2: Daily VWAP Engine** - Compute daily VWAP and volume-weighted expanding σ bands with cross-validation output
- [ ] **Phase 3: Simple Structural Levels** - Compute prior-day value area and detect price proximity to structural reference points
- [ ] **Phase 4: Setup Detection** - Identify candidate VWAP reversion setups by combining deviation, structural proximity, and time window filters
- [ ] **Phase 5: Trade Simulation Engine** - Simulate mechanical trade entry/exit with slippage, commissions, stops, and position management
- [ ] **Phase 6: Core Analytics & Output** - Produce trade log, compute performance metrics, and export results to CSV/JSON
- [ ] **Phase 7: Volume Profile Engine** - Build daily and HTF volume profiles with LVN detection, balance areas, and overnight value area
- [ ] **Phase 8: Regime & Multi-Timeframe VWAP** - Classify sessions by volatility regime and compute weekly/monthly VWAP anchors
- [ ] **Phase 9: Full Strategy Integration** - Add continuation failure detection, confluence scoring, and multi-target exit logic
- [ ] **Phase 10: Advanced Analytics** - Decompose results by regime, σ-band, time-of-day, equity curve, and reference comparison

## Phase Details

### Phase 1: Data Pipeline Foundation
**Goal**: Clean, session-structured, front-month NQ timeseries ready for indicator computation
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08
**Success Criteria** (what must be TRUE):
  1. System loads any of the 884 CSV files and returns only front-month NQ contract rows with correct data types
  2. System correctly identifies front-month contract across all ~12 quarterly rolls using volume-based detection without look-ahead
  3. All timestamps display in US/Eastern with correct DST handling (verifiable at known DST transition dates — 6 transitions in dataset)
  4. Session boundaries (RTH 9:30-16:00 ET, overnight 18:00-9:30 ET, full 24h) are correctly labeled for any given trading day
  5. First load converts CSV→Parquet and caches; subsequent loads of the full dataset complete in under 30 seconds
**Plans**: 3 plans
Plans:
- [ ] 01-01-PLAN.md - Bootstrap the Python package and typed raw-ingestion foundation
- [ ] 01-02-PLAN.md - Implement causal front-month mapping and ET session labeling
- [ ] 01-03-PLAN.md - Build canonical parquet cache, quality reporting, and Phase 1 CLI

### Phase 2: Daily VWAP Engine
**Goal**: Accurate daily VWAP and deviation bands that match reference charting platforms
**Depends on**: Phase 1
**Requirements**: VWAP-01, VWAP-02, VWAP-06
**Success Criteria** (what must be TRUE):
  1. Daily VWAP values match TradingView or NinjaTrader on at least 5 manually verified sessions (within 0.25 NQ points)
  2. Standard deviation bands (1σ-4σ) use the correct volume-weighted expanding formula — not rolling window std
  3. VWAP and band values are output in a format enabling side-by-side comparison with a reference platform
**Plans**: TBD

### Phase 3: Simple Structural Levels
**Goal**: Prior-day value area levels available as reference points for signal detection
**Depends on**: Phase 1
**Requirements**: STRC-01, STRC-07
**Success Criteria** (what must be TRUE):
  1. Prior-day VAH, VAL, and POC values are computed correctly for any session (verifiable against a volume profile chart)
  2. System detects when current price is within configurable proximity (default ±10 NQ points) of any structural level
**Plans**: TBD

### Phase 4: Setup Detection
**Goal**: System identifies candidate VWAP reversion setups during the trading window
**Depends on**: Phase 2, Phase 3
**Requirements**: VWAP-03, SGNL-01, SGNL-02, SGNL-03
**Success Criteria** (what must be TRUE):
  1. System filters to the configurable RTH trading window (default 9:30-11:30 ET) correctly across all sessions including DST transitions
  2. System detects when price is extended from VWAP within the configured deviation range (default 1.7σ-3.0σ)
  3. System identifies setups where VWAP extension AND structural level proximity coincide within the time window
  4. Each detected setup is logged with full context — sigma level, which structural level, timestamp, gamma regime (if available), bid/ask at signal
**Plans**: TBD

### Phase 5: Trade Simulation Engine
**Goal**: Mechanical trade replay producing realistic per-trade results with transaction cost modeling
**Depends on**: Phase 4
**Requirements**: TSIM-01, TSIM-02, TSIM-03, TSIM-04, TSIM-05, TSIM-07, TSIM-08
**Success Criteria** (what must be TRUE):
  1. System enters trades after setup conditions are met and exits at daily VWAP reversion target
  2. Every trade includes slippage (BBO spread-crossing cost + configurable additional impact) and round-trip commissions
  3. Only one position is open at a time — overlapping setups during an active trade are skipped
  4. Stop-loss triggers when maximum adverse excursion exceeds the configured threshold
  5. Any open position is force-closed at session end (16:00 ET)
**Plans**: TBD

### Phase 6: Core Analytics & Output
**Goal**: Backtest results quantified with standard performance metrics and exported for analysis
**Depends on**: Phase 5
**Requirements**: ANLY-01, ANLY-02, ANLY-03
**Success Criteria** (what must be TRUE):
  1. Trade log contains entry price, exit price, P&L in ticks and dollars, duration, sigma at entry, and structural level for every trade
  2. Core performance metrics computed — win rate, average win/loss ratio, profit factor, max drawdown, Sharpe ratio, total P&L
  3. Results exported to both structured CSV and JSON files
**Plans**: TBD

### Phase 7: Volume Profile Engine
**Goal**: Full structural level detection from daily and HTF volume profiles replacing simple prior-day VA proxy
**Depends on**: Phase 1
**Requirements**: STRC-02, STRC-03, STRC-04, STRC-05, STRC-06
**Success Criteria** (what must be TRUE):
  1. Daily volume profiles produce correct price×volume histograms at configurable tick resolution
  2. HTF 180-day rolling composite profile updates daily without look-ahead bias (uses only completed sessions)
  3. Low Volume Nodes (LVNs) detected from valleys in volume profile distribution
  4. Balance area extremes identified from HTF composite profile edges
  5. Overnight value area (VAH, VAL, POC) computed from globex session data before each RTH open
**Plans**: TBD

### Phase 8: Regime & Multi-Timeframe VWAP
**Goal**: Sessions classified by volatility regime and multi-timeframe VWAP anchors available for signal and target enrichment
**Depends on**: Phase 1
**Requirements**: REGM-01, REGM-02, REGM-03, VWAP-04, VWAP-05
**Success Criteria** (what must be TRUE):
  1. Realized volatility computed over configurable lookback window for each session
  2. Sessions classified as short gamma or long gamma — short gamma sessions show approximately 2.8x more setups and ~32% larger displacements (matching reference statistics)
  3. Regime-adjusted deviation thresholds applied (different selectivity per regime)
  4. Weekly VWAP rolls correctly across sessions within the trading week including across contract rolls
  5. Monthly VWAP rolls correctly across sessions within the calendar month including across contract rolls
**Plans**: TBD

### Phase 9: Full Strategy Integration
**Goal**: Strategy upgraded with all available indicators for high-fidelity setup detection and flexible trade management
**Depends on**: Phase 6, Phase 7, Phase 8
**Requirements**: SGNL-04, SGNL-05, TSIM-06
**Success Criteria** (what must be TRUE):
  1. System defines and applies mechanical continuation failure detection from BBO price action (rejection pattern, failed new high/low within N bars)
  2. Setups scored by multi-condition confluence — deviation magnitude, number of structural levels aligned, VWAP timeframe agreement
  3. Trades support multiple exit targets — daily VWAP (primary), weekly VWAP, developing POC
**Plans**: TBD

### Phase 10: Advanced Analytics
**Goal**: Results decomposed across every analytical dimension for comprehensive edge characterization
**Depends on**: Phase 9
**Requirements**: ANLY-04, ANLY-05, ANLY-06, ANLY-07, ANLY-08
**Success Criteria** (what must be TRUE):
  1. All performance metrics broken down by gamma regime (short vs long) with statistical comparison
  2. All performance metrics broken down by σ-band at entry (1.7-2.2σ, 2.2-3.0σ, 3.0σ+)
  3. All performance metrics broken down by time-of-day in 15-minute buckets within the trading window
  4. Equity curve data (cumulative P&L over time) exported for trend and drawdown analysis
  5. Backtest results compared against model author's reference statistics — median deviation ~2.0σ, return probabilities by band, displacement ratios by regime
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Pipeline Foundation | 0/3 | Planned | - |
| 2. Daily VWAP Engine | 0/? | Not started | - |
| 3. Simple Structural Levels | 0/? | Not started | - |
| 4. Setup Detection | 0/? | Not started | - |
| 5. Trade Simulation Engine | 0/? | Not started | - |
| 6. Core Analytics & Output | 0/? | Not started | - |
| 7. Volume Profile Engine | 0/? | Not started | - |
| 8. Regime & Multi-Timeframe VWAP | 0/? | Not started | - |
| 9. Full Strategy Integration | 0/? | Not started | - |
| 10. Advanced Analytics | 0/? | Not started | - |
