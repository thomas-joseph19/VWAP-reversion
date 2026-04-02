# Requirements: VWAP Reversion Backtester

**Defined:** 2026-04-01
**Core Value:** Accurately measure the statistical edge of NQ VWAP reversion trades at structural levels during early NY session — across volatility regimes.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Pipeline

- [x] **DATA-01**: System ingests CME Globex MDP3 BBO 1-second CSV files (one per trading day, ~884 files)
- [x] **DATA-02**: System identifies front-month NQ contract using volume-based detection (not nearest-expiration)
- [x] **DATA-03**: System handles quarterly contract rolls (March, June, September, December) with price gap management
- [x] **DATA-04**: System converts all timestamps from UTC to US/Eastern with correct DST handling (using zoneinfo, not pytz)
- [x] **DATA-05**: System defines session boundaries — RTH (9:30-16:00 ET), overnight/globex (18:00-9:30 ET), full 24h
- [x] **DATA-06**: System performs one-time CSV→Parquet conversion and caches results for 5-10x faster subsequent loads
- [x] **DATA-07**: System validates data schema on load and reports quality issues (missing fields, corrupt rows, unexpected symbols)
- [x] **DATA-08**: System detects data gaps (missing days, missing time intervals) and identifies market holidays

### VWAP & Deviation

- [ ] **VWAP-01**: System computes Daily VWAP from trade prints using price × volume weighting (not mid-price)
- [ ] **VWAP-02**: System computes volume-weighted expanding standard deviation bands (1σ through 4σ) from session anchor — NOT rolling window std dev
- [ ] **VWAP-03**: System detects when price is extended from VWAP within configurable deviation thresholds (default 1.7σ to 3.0σ)
- [ ] **VWAP-04**: System computes Weekly VWAP rolling across sessions within the trading week
- [ ] **VWAP-05**: System computes Monthly VWAP rolling across sessions within the calendar month
- [ ] **VWAP-06**: System outputs VWAP values in a format that can be cross-validated against a reference charting platform (e.g., TradingView, NinjaTrader)

### Structural Levels

- [ ] **STRC-01**: System computes prior-day value area — VAH, VAL, and POC — from trade volume distribution
- [ ] **STRC-02**: System computes overnight value area edges (globex session before RTH)
- [ ] **STRC-03**: System builds daily volume profiles (price × volume histogram at configurable tick resolution)
- [ ] **STRC-04**: System builds HTF volume profile (rolling 180-day composite) without look-ahead bias
- [ ] **STRC-05**: System identifies Low Volume Nodes (LVNs) from volume profiles
- [ ] **STRC-06**: System identifies balance area extremes from HTF volume profiles
- [ ] **STRC-07**: System detects when price is within configurable proximity of a structural level (default ±10 NQ points)

### Regime Classification

- [ ] **REGM-01**: System computes realized volatility over a configurable lookback window
- [ ] **REGM-02**: System classifies each session as short gamma or long gamma based on realized volatility thresholds
- [ ] **REGM-03**: System applies regime-adjusted expectations (different deviation thresholds and selectivity per regime)

### Signal Detection

- [ ] **SGNL-01**: System filters trading opportunities to the first 1-2 hours of RTH (configurable window, default 9:30-11:30 ET)
- [ ] **SGNL-02**: System detects combined conditions — price extended from VWAP AND at a structural level AND within the time window
- [ ] **SGNL-03**: System logs each detected setup with full context (sigma level, which structural level, time, regime, bid/ask at signal)
- [ ] **SGNL-04**: System defines mechanical continuation failure from BBO price action (rejection pattern, failed new high/low within N bars)
- [ ] **SGNL-05**: System scores setups by multi-condition confluence (deviation magnitude, number of structural levels aligned, VWAP timeframe agreement)

### Trade Simulation

- [ ] **TSIM-01**: System simulates trade entry after setup conditions are met (post-failure confirmation)
- [ ] **TSIM-02**: System exits trades at VWAP reversion targets (daily VWAP as primary)
- [ ] **TSIM-03**: System models slippage (spread-crossing cost from BBO + configurable additional impact)
- [ ] **TSIM-04**: System models round-trip commissions (configurable, default NQ standard rates)
- [ ] **TSIM-05**: System enforces one-trade-at-a-time position management (no overlapping positions)
- [ ] **TSIM-06**: System supports multi-target exits (daily VWAP, weekly VWAP, developing POC)
- [ ] **TSIM-07**: System applies stop-loss logic based on maximum adverse excursion thresholds
- [ ] **TSIM-08**: System exits any open position at session end (time-based forced exit)

### Analytics

- [ ] **ANLY-01**: System produces trade log with entry price, exit price, P&L (ticks and dollars), duration, sigma at entry, structural level, regime
- [ ] **ANLY-02**: System computes core performance metrics — win rate, average win/loss, profit factor, max drawdown, Sharpe ratio, total P&L
- [ ] **ANLY-03**: System outputs results to structured CSV and JSON files
- [ ] **ANLY-04**: System breaks down all metrics by gamma regime (short vs long)
- [ ] **ANLY-05**: System breaks down all metrics by σ-band at entry (1.7-2.2σ, 2.2-3.0σ, 3.0σ+)
- [ ] **ANLY-06**: System breaks down all metrics by time-of-day (e.g., 15-minute buckets within trading window)
- [ ] **ANLY-07**: System outputs equity curve data (cumulative P&L over time)
- [ ] **ANLY-08**: System compares backtest results against model author's reference statistics (median deviation ~2.0σ, return probabilities by band, displacement by regime)

## v2 Requirements

Machine learning enhancement of the mechanical model.

### ML / Optimization

- **ML-01**: Feature engineering pipeline extracting predictive signals from backtest data (sigma, structural confluence, regime, time, BBO microstructure)
- **ML-02**: Classification model to predict setup quality (high/low probability of reversion)
- **ML-03**: Reinforcement learning or supervised approach to optimize entry timing and target selection
- **ML-04**: Out-of-sample validation framework with walk-forward testing
- **ML-05**: Parameter sensitivity analysis across strategy parameters
- **ML-06**: Feature importance analysis to identify which conditions most predict successful reversion

### Advanced Analytics

- **ADV-01**: Trade visualization export (charts showing entry/exit on price with VWAP/bands)
- **ADV-02**: Monte Carlo simulation for drawdown probability estimation
- **ADV-03**: Rolling window performance analysis (strategy stability over time)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Live execution / order routing | Backtest only — no broker integration |
| Orderflow confirmation (DOM/tape) | Not available in BBO data; mechanical proxy used instead |
| ES or other instruments | NQ front month only for v1 |
| Options/GEX data integration | Gamma regime derived from realized vol proxy |
| GUI / dashboard | Command-line backtest with file output |
| Real-time streaming | Historical replay only |
| Multi-strategy support | Single strategy engine |
| Database storage | File-based I/O sufficient for research tool |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| DATA-06 | Phase 1 | Complete |
| DATA-07 | Phase 1 | Complete |
| DATA-08 | Phase 1 | Complete |
| VWAP-01 | Phase 2 | Pending |
| VWAP-02 | Phase 2 | Pending |
| VWAP-03 | Phase 4 | Pending |
| VWAP-04 | Phase 8 | Pending |
| VWAP-05 | Phase 8 | Pending |
| VWAP-06 | Phase 2 | Pending |
| STRC-01 | Phase 3 | Pending |
| STRC-02 | Phase 7 | Pending |
| STRC-03 | Phase 7 | Pending |
| STRC-04 | Phase 7 | Pending |
| STRC-05 | Phase 7 | Pending |
| STRC-06 | Phase 7 | Pending |
| STRC-07 | Phase 3 | Pending |
| REGM-01 | Phase 8 | Pending |
| REGM-02 | Phase 8 | Pending |
| REGM-03 | Phase 8 | Pending |
| SGNL-01 | Phase 4 | Pending |
| SGNL-02 | Phase 4 | Pending |
| SGNL-03 | Phase 4 | Pending |
| SGNL-04 | Phase 9 | Pending |
| SGNL-05 | Phase 9 | Pending |
| TSIM-01 | Phase 5 | Pending |
| TSIM-02 | Phase 5 | Pending |
| TSIM-03 | Phase 5 | Pending |
| TSIM-04 | Phase 5 | Pending |
| TSIM-05 | Phase 5 | Pending |
| TSIM-06 | Phase 9 | Pending |
| TSIM-07 | Phase 5 | Pending |
| TSIM-08 | Phase 5 | Pending |
| ANLY-01 | Phase 6 | Pending |
| ANLY-02 | Phase 6 | Pending |
| ANLY-03 | Phase 6 | Pending |
| ANLY-04 | Phase 10 | Pending |
| ANLY-05 | Phase 10 | Pending |
| ANLY-06 | Phase 10 | Pending |
| ANLY-07 | Phase 10 | Pending |
| ANLY-08 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 45 total
- Mapped to phases: 45
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-02 after Phase 1 completion*
