# Phase 6: Core Analytics & Output - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 06-core-analytics-output
**Areas discussed:** Analytics input contract, Metric definitions, Output surfaces, CLI and workflow integration

---

## Analytics input contract

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 5 trade log | Build analytics directly from the deterministic Phase 5 trade-log artifact and derive only missing analysis columns | x |
| Re-simulate from Phase 4 | Rebuild trades during analytics generation for tighter coupling between metrics and replay logic | |
| Hybrid rebuild | Mix Phase 5 outputs with selective recomputation from earlier phase artifacts | |

**User's choice:** Auto-selected recommended default: reuse the Phase 5 trade log as the canonical analytics input.
**Notes:** This matches the repo's phase-to-phase artifact handoff pattern and avoids duplicating replay logic.

---

## Metric definitions

| Option | Description | Selected |
|--------|-------------|----------|
| Net-dollar baseline | Compute headline metrics from `net_dollars` while also exposing points/ticks per trade | x |
| Gross-points baseline | Use pre-cost point economics as the primary measure and treat costs as secondary metadata | |
| Dual-equal basis | Treat gross points and net dollars as equal first-class metric bases throughout | |

**User's choice:** Auto-selected recommended default: net-dollar baseline with derived point/tick trade fields.
**Notes:** This keeps Phase 6 aligned with the cost-aware economics already locked in Phase 5.

---

## Output surfaces

| Option | Description | Selected |
|--------|-------------|----------|
| CSV trade log + JSON metrics | Export row-level trades to CSV and aggregate metrics to JSON from the same deterministic input snapshot | x |
| JSON only | Store both trades and summary metrics in JSON artifacts only | |
| CSV only | Export all outputs as tables and skip structured summary JSON | |

**User's choice:** Auto-selected recommended default: CSV trade log plus JSON metrics.
**Notes:** This best matches the roadmap's structured-output requirement and the repo's existing validation-artifact style.

---

## CLI and workflow integration

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated Phase 6 command | Add a new builder command that consumes Phase 5 outputs and writes a self-contained analytics directory | x |
| Fold into Phase 5 command | Extend the existing Phase 5 command to optionally compute analytics too | |
| Test-only helper | Leave analytics generation as a library call without first-class CLI wiring | |

**User's choice:** Auto-selected recommended default: dedicated Phase 6 command.
**Notes:** This preserves the one-phase/one-builder pattern already used by Phases 1-5.

---

## the agent's Discretion

- Exact artifact names and manifest structure for Phase 6 outputs.
- Exact Sharpe scaling/null policy, as long as it is documented.

## Deferred Ideas

- Advanced breakdowns by regime, sigma bucket, and time bucket are deferred to Phase 10.
- Strategy variations requiring new targets or continuation rules are deferred to later phases.
