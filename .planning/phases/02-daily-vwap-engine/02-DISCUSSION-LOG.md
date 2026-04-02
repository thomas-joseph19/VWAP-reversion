# Phase 2: Daily VWAP Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-02T00:00:00-04:00
**Phase:** 02-daily-vwap-engine
**Areas discussed:** Session anchor and reset policy, Price and volume inputs, Sigma-band methodology, Output and validation surface

---

## Session anchor and reset policy

| Option | Description | Selected |
|--------|-------------|----------|
| RTH anchored | Reset at 9:30 AM ET and compute from the regular session only so the indicator matches the strategy's early-session fair-value reference. | yes |
| Globex anchored | Reset from the 6:00 PM ET overnight open and include overnight trade flow in the daily anchor. | |
| Calendar anchored | Reset on a UTC or local calendar boundary for simpler bookkeeping. | |

**User's choice:** `[auto]` Selected `RTH anchored` as the recommended default.
**Notes:** The existing research explicitly flags the anchor as the key Phase 2 gray area and recommends resolving it before implementation. The default chosen here aligns the indicator with the project's RTH reversion use case and chart-validation goal.

---

## Price and volume inputs

| Option | Description | Selected |
|--------|-------------|----------|
| Trade-only inputs | Use only rows with actual trades (`side` in `B` or `A`) and forward-fill indicator values through no-trade seconds. | yes |
| Mid-price imputation | Use quote mid-price plus minimal synthetic size during no-trade intervals to avoid indicator gaps. | |
| Hybrid mode | Compute both variants and make the baseline configurable from day one. | |

**User's choice:** `[auto]` Selected `Trade-only inputs` as the recommended default.
**Notes:** Repo research treats mid-price imputation as a sensitivity path, not the baseline. Phase 2 locks the canonical implementation to actual trade volume so platform comparisons remain interpretable.

---

## Sigma-band methodology

| Option | Description | Selected |
|--------|-------------|----------|
| Expanding volume-weighted sigma | Use cumulative `sum(v*p^2)`, `sum(v*p)`, and `sum(v)` from the session anchor; publish 1-4 sigma bands. | yes |
| Rolling window std | Use a conventional rolling standard deviation around the session VWAP. | |
| Library helper | Delegate the sigma calculation to a generic indicator/statistics helper API. | |

**User's choice:** `[auto]` Selected `Expanding volume-weighted sigma` as the recommended default.
**Notes:** This is the most strongly supported requirement in the planning research and is necessary to avoid the documented rolling-std failure mode.

---

## Output and validation surface

| Option | Description | Selected |
|--------|-------------|----------|
| Reusable indicator dataset + validation artifact | Keep row-aligned VWAP/band columns for downstream phases and emit a manual cross-check report for at least five sessions. | yes |
| Validation only | Focus on ad-hoc chart checks without persisting a structured artifact for downstream review. | |
| Separate comparison-only export | Produce a comparison artifact but avoid preserving a reusable indicator dataset. | |

**User's choice:** `[auto]` Selected `Reusable indicator dataset + validation artifact` as the recommended default.
**Notes:** This matches the established artifact-driven workflow from Phase 1 and keeps Phase 2 useful for downstream signal phases.

---

## the agent's Discretion

- Exact file/module split for the new indicator implementation.
- Exact report schema for the manual validation artifact.
- Exact persistence format for the reusable Phase 2 output, as long as it remains deterministic and audit-friendly.

## Deferred Ideas

- Overnight-inclusive daily VWAP sensitivity study.
- Weekly/monthly VWAP decisions across contract rolls for Phase 8.
