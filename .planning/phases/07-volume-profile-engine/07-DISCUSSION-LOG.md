# Phase 7: Volume Profile Engine - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-02
**Phase:** 07-volume-profile-engine
**Areas discussed:** Profile session scope, Price bucketing and level extraction, HTF composite outputs, Artifact shape

---

## Profile session scope

| Option | Description | Selected |
|--------|-------------|----------|
| Prior-day RTH only | Extend the Phase 3 baseline without adding overnight or HTF references yet. | |
| Overnight + prior-day + prior-only HTF composite | Build the full completed-session structural set while keeping every row causal at the RTH open. | x |
| Developing same-day profiles | Include same-session developing RTH profile levels for intraday structure updates. | |

**User's choice:** `[auto] Overnight + prior-day + prior-only HTF composite`
**Notes:** Recommended default because it satisfies the full Phase 7 goal while preserving the causality guarantees already established in earlier phases.

---

## Price bucketing and level extraction

| Option | Description | Selected |
|--------|-------------|----------|
| One-tick buckets + Phase 3 value-area rules + stable LVN minima | Preserve NQ tick granularity, keep deterministic value-area logic, and add lightly smoothed LVN extraction. | x |
| Wider custom buckets | Aggregate prices into larger bins to reduce noise and artifact size. | |
| Adaptive buckets and aggressive node detection | Use variable bin widths and very sensitive LVN detection for more levels. | |

**User's choice:** `[auto] One-tick buckets + Phase 3 value-area rules + stable LVN minima`
**Notes:** Recommended default because it stays compatible with existing structural artifacts and avoids making irreversible aggregation choices too early.

---

## HTF composite outputs

| Option | Description | Selected |
|--------|-------------|----------|
| Rolling 180-day RTH composite with HTF `POC`, `VAH`, `VAL`, and LVNs | Match the roadmap directly and surface reusable higher-timeframe references. | x |
| Rolling 30-day composite | Start with a shorter history for faster iteration and fewer long-memory effects. | |
| Full-history composite | Use all available completed sessions for one global structural map. | |

**User's choice:** `[auto] Rolling 180-day RTH composite with HTF POC/VAH/VAL/LVNs`
**Notes:** Recommended default because the roadmap explicitly calls for a rolling 180-day higher-timeframe composite without look-ahead bias.

---

## Artifact shape

| Option | Description | Selected |
|--------|-------------|----------|
| Per-profile parquet artifacts + row-aligned enriched dataset + validation exports | Follow the repo's existing phase output pattern and keep downstream consumption simple. | x |
| Row-aligned dataset only | Skip dedicated profile artifacts and only emit enriched rows. | |
| Summary reports only | Focus on human-readable outputs and defer reusable machine-readable datasets. | |

**User's choice:** `[auto] Per-profile parquet artifacts + row-aligned enriched dataset + validation exports`
**Notes:** Recommended default because later phases need reusable numeric structure, not just summaries, and the existing CLI/artifact pattern already supports this shape well.

---

## the agent's Discretion

- Exact LVN smoothing and prominence thresholds.
- Precise artifact filenames and helper/module boundaries.
- Additional audit-friendly metadata columns for profile coverage and composite windows.

## Deferred Ideas

- Developing same-session RTH profiles for intraday dynamic structure.
- Regime-aware structural thresholds and VWAP confluence.
- Continuation-failure and richer signal-scoring behavior.
