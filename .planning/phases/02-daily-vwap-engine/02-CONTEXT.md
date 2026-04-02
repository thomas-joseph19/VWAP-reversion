# Phase 2: Daily VWAP Engine - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the daily VWAP indicator layer on top of the Phase 1 canonical front-month dataset so downstream phases can measure intraday extension from fair value using a chart-validated, strictly causal, session-anchored VWAP and volume-weighted expanding sigma bands. Weekly/monthly VWAP, structural levels, regime logic, and trade simulation remain out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Session anchor and reset policy
- **D-01:** Anchor the daily VWAP and sigma calculations to the regular trading hours open at 9:30 AM America/New_York for each `trading_date`, not midnight UTC and not the 6:00 PM ET Globex open.
- **D-02:** Compute the Phase 2 indicator from RTH-only trade flow so the VWAP reference matches the strategy's early-session reversion lens and can be cross-validated against an RTH session VWAP on charting platforms.
- **D-03:** Treat the first eligible RTH trade of each session as the initial VWAP observation; before that trade arrives, indicator values may remain null within the session rather than synthesizing a pre-trade anchor.

### Price and volume inputs
- **D-04:** Use actual trade-print rows only (`side` in `B` or `A`) as VWAP inputs, with `price * size` and `size` as the cumulative numerators/denominator.
- **D-05:** Do not use BBO mid-price rows as synthetic trade inputs for Phase 2; when no trade occurs in a given second, carry the most recent VWAP and sigma values forward instead of imputing volume.
- **D-06:** Base indicator ordering and session membership on the Phase 1 canonical session-labeled dataset so DST handling and contract selection remain inherited, not reimplemented inside the VWAP engine.

### Sigma-band methodology
- **D-07:** Implement sigma as the volume-weighted expanding standard deviation from the same session anchor using cumulative `sum(volume * price^2)`, `sum(volume * price)`, and `sum(volume)`, never a rolling-window standard deviation.
- **D-08:** Publish 1 sigma through 4 sigma upper and lower bands from the computed session VWAP and expanding sigma so later phases can use the exact same columns for signal detection.
- **D-09:** Preserve strict causality: each row's VWAP and sigma may use only observations at or before that row's timestamp, with no full-session replay or future leakage.

### Output and validation surface
- **D-10:** Materialize the Phase 2 output as a reusable indicator dataset keyed to the canonical Phase 1 timeseries, with VWAP and band columns aligned row-for-row so later phases can join by existing timestamps without additional reshaping.
- **D-11:** Produce a cross-validation artifact for manually checked sessions that records timestamped VWAP and sigma-band values in a side-by-side friendly format for TradingView or NinjaTrader comparisons.
- **D-12:** Validate on at least five manually chosen sessions spanning ordinary days and DST-adjacent periods, and treat a mismatch beyond 0.25 NQ points as a blocking defect for Phase 2 completion.

### the agent's Discretion
- Exact module names and package boundaries for the new indicator code, as long as the Phase 1 package structure stays coherent.
- Whether the reusable output is persisted as a new parquet dataset, sibling artifact set, or a deterministic rebuildable command output.
- The precise schema of the cross-validation report, provided it supports side-by-side timestamp comparisons.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 2 goal, dependency boundary, and success criteria for chart-matched daily VWAP plus sigma bands.
- `.planning/REQUIREMENTS.md` - VWAP-01, VWAP-02, and VWAP-06 requirements that define trade-only weighting, expanding sigma, and validation output expectations.
- `.planning/PROJECT.md` - Project-level constraints, data semantics, and the pending Phase 2 anchor decision that this context now resolves.
- `.planning/STATE.md` - Current milestone state showing Phase 2 as the active focus.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked decisions around `ts_recv` ordering, ET session labels, `trading_date`, and canonical parquet cache layout that Phase 2 must inherit.

### Research and implementation guidance
- `.planning/research/SUMMARY.md` - Recommended stack, vectorized pipeline shape, and Phase 2 rationale emphasizing causal VWAP correctness over premature optimization.
- `.planning/research/PITFALLS.md` - Domain pitfalls for wrong sigma formula, wrong session anchor, look-ahead bias, and trade-vs-mid-price handling.
- `.planning/research/ARCHITECTURE.md` - Proposed indicator-engine structure, dataflow, and anti-pattern guidance for keeping indicator columns on the main dataframe.
- `.planning/research/STACK.md` - Stack expectations for Polars plus NumPy-based cumulative math and the supporting test/tooling choices for indicator validation.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/data_pipeline/cache.py`: exposes `scan_canonical_cache()` for lazy reuse of the Phase 1 canonical parquet dataset as the Phase 2 input surface.
- `src/vwap_revert/data_pipeline/sessions.py`: already provides ET-local timestamps, `trading_date`, and RTH/overnight flags that should gate the session anchor logic instead of recomputing calendars.
- `src/vwap_revert/cli.py`: establishes the existing CLI pattern for phase-scoped commands and artifact emission, which Phase 2 can extend with a new subcommand rather than introducing a second entrypoint style.

### Established Patterns
- The codebase is Polars-first for tabular orchestration and uses explicit artifact writers instead of hidden side effects.
- Phase 1 established one canonical parquet cache plus sibling audit artifacts, so Phase 2 should prefer deterministic, inspectable outputs over in-memory-only indicator calculations.
- Project research consistently favors vectorized transforms and cumulative math over framework abstractions or rolling-stat helper APIs.

### Integration Points
- Phase 2 should load from the canonical cache produced by Phase 1 and append indicator columns without changing front-month or session-selection rules.
- The resulting VWAP/band dataset becomes a direct dependency for Phase 4 setup detection and an indirect dependency for later simulation and analytics phases.
- Cross-validation artifacts should live near other phase outputs so manual review of platform comparisons is part of the audit trail.

</code_context>

<specifics>
## Specific Ideas

- Auto-selected default: use RTH-only daily VWAP anchored at 9:30 ET because the strategy tests early-session mean reversion against the session fair-value reference, and the repo research warns that overnight-inclusive anchors materially change the indicator.
- Auto-selected default: compute VWAP from trade prints only and forward-fill through no-trade seconds rather than injecting synthetic mid-price volume.
- Auto-selected default: validate the manual comparison set with a side-by-side artifact that includes timestamps, last trade price, VWAP, sigma, and 1-4 sigma bands for at least five sessions.

</specifics>

<deferred>
## Deferred Ideas

- Overnight-inclusive daily VWAP variants for sensitivity analysis - possible future research, but not part of the baseline Phase 2 deliverable.
- Weekly and monthly VWAP handling across contract rolls - explicitly deferred to Phase 8.

</deferred>

---

*Phase: 02-daily-vwap-engine*
*Context gathered: 2026-04-02*
