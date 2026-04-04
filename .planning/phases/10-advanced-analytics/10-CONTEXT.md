# 10-CONTEXT: Advanced Analytics

## Boundary & Goals
Implement advanced performance decomposition and equity curve analysis for Phase 09 strategy results.

## Key Requirements
- **REGM-01 Breakdown**: Statistical comparison of performance across Short Gamma vs Long Gamma regimes.
- **SIGM-01 Breakdown**: Performance attribution by entry Sigma magnitude (1.7-2.2, 2.2-3.0, 3.0+).
- **TIME-01 Breakdown**: Intraday performance attribution in 15-minute buckets.
- **EQTY-01**: Export of cumulative P&L time series (Equity Curve) for external drawdown analysis.

## Implementation Decisions
- **Vectorized Breakdown**: Use Polars `group_by` on the primary `trade_log` to generate sub-metrics.
- **Bucket Definitions**:
    - **Sigma Bands**: [1.7, 2.2), [2.2, 3.0), [3.0, inf).
    - **Time Buckets**: Truncate `entry_ts` to 15-minute intervals.
- **Artifacts**: Produce a comprehensive `phase10_analytics_report.json` containing nested breakdowns and a `phase10_equity_curve.parquet`.

## Canonical References
- **Requirements**: ANLY-04, ANLY-05, ANLY-06, ANLY-07, ANLY-08
- **Source**: `src/vwap_revert/analytics.py`
- **Output**: `phase10_analytics_report.json`, `phase10_equity_curve.parquet`
