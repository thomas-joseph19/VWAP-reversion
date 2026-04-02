# Phase 3: Simple Structural Levels - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 03-simple-structural-levels
**Areas discussed:** Profile construction, Session scope, Proximity logic, Outputs and validation

---

## Profile Construction

| Option | Description | Selected |
|--------|-------------|----------|
| Native traded price levels | Use the highest-resolution traded prices available from the 1-second BBO-derived trade rows so later analytics and ML can derive their own aggregations | ✓ |
| Coarser custom buckets | Aggregate into wider bins up front for simpler baseline profile math | |
| User-specified profile method later | Defer the decision to planning/implementation after more prompting | |

**User's choice:** "i have bbo-1s data, so whatever we can do with that... do whatever you think is best and will set us up best for future machine learning"
**Notes:** Chose the highest-information baseline compatible with the existing dataset. This preserves optionality for later feature engineering instead of forcing an early lossy bucketing scheme.

---

## Session Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Prior RTH session only | Align structural levels with the actual trading model and the Phase 2 RTH VWAP anchor | ✓ |
| Full 24-hour prior session | Build structural levels from the entire prior trading day including overnight activity | |
| Prior overnight/globex profile | Use overnight structure ahead of the RTH open | |

**User's choice:** "outside of that, we're only trading during rth right? whatever the model is i kinda forget"
**Notes:** Interpreted as approval to stay aligned with the current RTH-only strategy baseline. Overnight-specific structure is captured as a later-phase deferment.

---

## Proximity Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Numeric-feature-first proximity | Emit signed distances, nearest level metadata, and boolean flags using an inclusive default threshold for downstream rule logic and ML | ✓ |
| Boolean-only proximity | Emit only yes/no within-threshold flags for each structural level | |
| Human-review-first output | Focus on chart review exports first and add machine-readable features later | |

**User's choice:** Delegated to the agent
**Notes:** Selected a feature-rich output because it best supports both Phase 4 rule-based setup detection and future ML work without recomputation.

---

## Outputs and Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Session artifact + row-aligned enrichment | Store per-session prior-day levels and also enrich each current-session row with active structural features | ✓ |
| Session artifact only | Keep a single per-session table and let later phases join it themselves | |
| Validation export only | Produce only chart-comparison output during this phase | |

**User's choice:** Delegated to the agent
**Notes:** Selected both artifact layers so downstream phases can choose convenience or compactness without rebuilding the profile logic. Validation remains focused on prior-day RTH value-area checks against reference charts.

---

## the agent's Discretion

- Exact implementation modules and CLI wiring.
- Deterministic tie-break details for `POC` and value-area expansion.
- Additional audit/report columns for missing or unusable prior sessions.

## Deferred Ideas

- Overnight value area and broader volume-profile structure are deferred to Phase 7.
