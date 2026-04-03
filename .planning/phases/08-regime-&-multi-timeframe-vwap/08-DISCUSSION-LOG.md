# Phase 8: Regime & Multi-Timeframe VWAP - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-03
**Phase:** 08-regime-&-multi-timeframe-vwap
**Areas discussed:** Regime classification policy, higher-timeframe VWAP semantics, artifact shape

---

## Regime classification policy

| Option | Description | Selected |
|--------|-------------|----------|
| Prior-session causal regime | Classify each trading date from rolling realized-volatility history built from prior completed sessions only. | x |
| Same-day full-session regime | Label the session from its own completed volatility, even though that would not be known during the early setup window. | |
| Manual date list | Maintain hand-authored regime dates outside the indicator pipeline. | |

**User's choice:** `[auto]` Prior-session causal regime.
**Notes:** Chosen because Phase 4/5 setups fire during 9:30-11:30 ET and need a label that is already known without look-ahead. The exact volatility formula and threshold rule remain planner/research discretion as long as they are deterministic and exposed in metadata.

---

## Higher-timeframe VWAP semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Extend Phase 2 semantics | Use RTH-only trade rows, cumulative `price * size` weighting, null-before-anchor behavior, and forward-fill alignment for weekly/monthly VWAP. | x |
| Introduce a new anchor model | Use a different price source or include overnight prints for higher-timeframe anchors. | |
| Precomputed session-level anchors only | Emit session summaries without row-aligned weekly/monthly VWAP columns. | |

**User's choice:** `[auto]` Extend Phase 2 semantics.
**Notes:** Chosen to keep higher-timeframe anchors consistent with the existing daily VWAP contract and avoid downstream schema/behavior drift.

---

## Artifact shape

| Option | Description | Selected |
|--------|-------------|----------|
| Row-level + session-level outputs | Write one enriched parquet for row-level consumers and one compact session summary for regime review and validation. | x |
| Row-level only | Keep all regime/session information embedded only in the enriched parquet. | |
| Session-level only | Emit regime and anchor summaries without a reusable row-aligned dataset. | |

**User's choice:** `[auto]` Row-level + session-level outputs.
**Notes:** Chosen because later strategy work needs row-level enrichment while manual review of regime decisions is easier from a compact session artifact.

---

## the agent's Discretion

- Exact realized-volatility formula and lookback length.
- Exact thresholding rule for converting realized-volatility values into binary regime labels.
- Additional audit columns beyond the baseline row-level and session-level contracts.

## Deferred Ideas

- Regime-adjusted threshold tuning belongs to later execution work once the baseline labels exist.
- Continuation-failure logic and multi-target exits belong to Phase 9.
- Regime/sigma/time-of-day analytics breakdowns belong to Phase 10.
