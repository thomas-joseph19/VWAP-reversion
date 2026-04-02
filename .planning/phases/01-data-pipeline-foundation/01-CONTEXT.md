# Phase 1: Data Pipeline Foundation - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the ingestion and normalization layer for CME Globex MDP3 1-second BBO files so downstream phases can consume a clean, front-month NQ dataset with correct Eastern timestamps, trading-session labels, and fast cached parquet reads. VWAP, structural levels, and strategy logic remain out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Front-month detection
- **D-01:** Determine the active NQ contract per trading day using same-day traded volume aggregated by outright contract symbol only, never nearest-expiry rules.
- **D-02:** Use a no-look-ahead daily mapping: each day selects the contract with the highest completed-day trade volume, and that mapping is the only contract exposed for that day's normalized dataset.
- **D-03:** Treat quarterly roll transitions as an explicit daily contract-map artifact so downstream phases can audit when the active symbol changed and handle discontinuities intentionally instead of blending contracts silently.

### Session and calendar labeling
- **D-04:** Convert all timestamps with `zoneinfo` to `America/New_York` and treat this as the canonical analysis timezone for every downstream dataset.
- **D-05:** Define the trading day by the Globex evening boundary: rows from 18:00 ET through the following 16:59:59 ET belong to the same trading date, with the 17:00-17:59 maintenance window excluded from session buckets.
- **D-06:** Emit row-level labels for `trading_date`, `session_name` (`overnight`, `rth`, `maintenance`), and boolean session flags so later phases can filter without recomputing calendar logic.

### Cache and file layout
- **D-07:** Build one canonical normalized parquet cache as the phase-1 source of truth rather than multiple partially overlapping datasets.
- **D-08:** Store parquet output partitioned by `trading_date` so reprocessing, spot validation, and partial reloads stay cheap while still supporting whole-history scans.
- **D-09:** Keep auxiliary artifacts alongside the canonical cache: a contract-roll map, schema summary, and data-quality report files for auditability.

### Data quality policy
- **D-10:** Fail fast on structural issues that would invalidate research output: missing required columns, unreadable files, timestamp parse failures, or inability to determine a front-month contract for a day.
- **D-11:** Tolerate recoverable row-level issues by dropping the affected rows and recording counts plus examples in a quality report; do not let a handful of bad rows abort the full historical build.
- **D-12:** Detect and report missing trading days, missing intraday intervals, and holiday/early-close anomalies explicitly, but preserve the available data unless the gap makes the day unusable under a documented threshold chosen during planning.

### the agent's Discretion
- Exact parquet engine and compression choice.
- Specific quality thresholds for declaring a day unusable.
- Internal module boundaries, function names, and report formatting.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/ROADMAP.md` - Phase 1 goal, dependency boundary, and success criteria.
- `.planning/REQUIREMENTS.md` - DATA-01 through DATA-08 acceptance requirements for ingestion, rolls, timestamps, sessions, caching, and quality checks.
- `.planning/PROJECT.md` - Dataset source details, field definitions, and project-level constraints for NQ-only research.
- `.planning/STATE.md` - Current execution state showing Phase 1 is the active focus.

### External specs
- No external specs - requirements are fully captured in decisions above and the planning documents listed here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No application code exists yet; Phase 1 will establish the initial Python data pipeline foundation.
- `.planning/research/STACK.md` indicates the project expects a Python stack centered on Polars/NumPy/Numba, which should guide implementation choices during planning.

### Established Patterns
- Project decisions already favor a custom vectorized pipeline over a backtesting framework.
- Planning artifacts consistently separate data foundation work from indicator and strategy phases, so phase output should be reusable, audit-friendly, and independent of trading logic.

### Integration Points
- Phase 2 will consume the normalized parquet dataset to compute daily VWAP and sigma bands.
- Phase 3 will consume the same session-aware dataset to compute prior-day value area levels.
- Quality reports and contract maps from this phase should be available to all later phases as reference inputs.

</code_context>

<specifics>
## Specific Ideas

- Optimize Phase 1 for reproducibility and auditability over clever roll heuristics; later research depends on trusting this dataset.
- Prefer explicit artifacts for contract mapping and data quality so validation against known DST transitions and roll dates is easy.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 01-data-pipeline-foundation*
*Context gathered: 2026-04-02*
