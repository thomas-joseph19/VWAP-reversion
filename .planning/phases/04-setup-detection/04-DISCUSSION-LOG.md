# Phase 4: Setup Detection - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the auto-selected defaults.

**Date:** 2026-04-02
**Phase:** 04-setup-detection
**Areas discussed:** Trading-window gating, VWAP-extension semantics, Structural confluence and candidate emission, Output artifacts and logged context

---

## Trading-window gating

| Option | Description | Selected |
|--------|-------------|----------|
| Default early-RTH window | Use a configurable `09:30-11:30 ET` window on existing `ts_recv_et` rows and preserve explicit pass/fail flags for auditing. | x |
| Full-session scan | Evaluate setups during all RTH hours. | |
| Custom per-day logic | Rebuild session gating from scratch inside Phase 4. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Matches the roadmap's stated early-session focus and reuses earlier session-label decisions.

---

## VWAP-extension semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Signed sigma-distance | Compute signed extension from actionable price versus `daily_vwap` and `daily_sigma`, with inclusive default thresholds `1.7-3.0`. | x |
| Raw point distance only | Use absolute point distance from VWAP without sigma normalization. | |
| Boolean-only extension | Persist only an in-range flag and no reusable numeric feature. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Keeps the output useful for later trade simulation and analytics while staying aligned with the strategy's sigma framing.

---

## Structural confluence and candidate emission

| Option | Description | Selected |
|--------|-------------|----------|
| Transition-based candidate log | Emit one setup when the combined predicate first becomes true for a contiguous episode. | x |
| Every qualifying row | Log every second that remains in a qualifying state. | |
| End-of-episode only | Wait until the state turns false and emit a summarized setup. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Avoids duplicate downstream trades and keeps the setup log deterministic.

---

## Output artifacts and logged context

| Option | Description | Selected |
|--------|-------------|----------|
| Row-aligned parquet plus compact setup log | Keep a reusable enriched dataset and a one-row-per-setup artifact with bid/ask, sigma, and structural context. | x |
| Setup log only | Emit only the compact event log. | |
| Human-readable report only | Emit CSV/report summaries without reusable row-level features. | |

**User's choice:** Auto-selected recommended default.
**Notes:** Matches the artifact-oriented pattern established in Phases 2 and 3.

---

## the agent's Discretion

- Exact helper/module split between enrichment and setup extraction.
- Additional diagnostic columns that improve auditability without changing the emitted setup semantics.

## Deferred Ideas

- Continuation-failure confirmation belongs to Phase 9.
- Regime-adjusted setup thresholds belong to Phase 8.
- Multi-condition confluence scoring belongs to later strategy-integration work.
