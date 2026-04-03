# Phase 7: Volume Profile Engine - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the structural-profile layer that replaces the Phase 3 prior-day proxy with deterministic daily, overnight, and higher-timeframe volume-profile references derived from the Phase 1 canonical NQ dataset. This phase delivers reusable profile artifacts and row-aligned structural columns for later setup, trade, and analytics phases; regime classification, weekly/monthly VWAP, continuation-failure logic, and multi-target execution remain out of scope.

</domain>

<decisions>
## Implementation Decisions

### Profile session scope and causality
- **D-01:** Compute three distinct completed-session profile families from trade-bearing rows only: prior completed RTH daily profiles keyed by `trading_date`, same-day overnight profiles covering the Globex session from 18:00 ET through the 9:29:59 ET pre-open boundary, and a rolling HTF composite built from prior completed daily RTH profiles only.
- **D-02:** Preserve strict causality for every structural reference: rows on trading date `T` may use the overnight profile completed before that day's RTH open, the prior completed daily profile from `T-1`, and HTF composites built from completed sessions strictly earlier than `T`; same-session developing RTH profiles must not leak into the row-aligned features.
- **D-03:** Reuse the Phase 1 `trading_date`, `is_overnight`, and `is_rth` labels as the only session boundary source so DST handling, maintenance-window exclusion, and contract selection stay inherited rather than reimplemented in this phase.

### Price bucketing and level extraction
- **D-04:** Build histograms on a configurable price bucket size that defaults to one NQ tick (`0.25` points), snapping trade prices onto a deterministic tick grid so all emitted structural levels remain compatible with later trade simulation and chart validation.
- **D-05:** Keep the Phase 3 value-area definition for all completed profiles: `POC` is the highest-volume bucket with the same deterministic fair-value and lower-price tie breaks, and `VAH`/`VAL` expand contiguously to the 70% target using stable adjacent-volume tie breaks.
- **D-06:** Detect LVNs from completed profile histograms using a lightly smoothed local-minimum rule with deterministic prominence thresholds, favoring stable, repeatable nodes over ultra-sensitive single-bucket noise; expose the detected node prices as numeric references rather than only human-readable annotations.

### HTF composite structure and downstream features
- **D-07:** Define the HTF profile as a rolling 180-trading-day composite of completed daily RTH histograms, updated once per trading date without look-ahead bias and rebuilt deterministically from the canonical cache rather than incrementally mutating hidden state.
- **D-08:** Derive HTF balance-area extremes from the composite profile's completed value-area boundaries and publish the corresponding HTF `POC`, `VAH`, `VAL`, and LVN references so later phases can score structural confluence against both local and higher-timeframe context.
- **D-09:** Emit row-aligned Phase 7 features that forward-carry the active overnight, prior-day daily, and HTF structural references onto each canonical row, including numeric distances, nearest-level labels, and explicit quality/status fields so Phase 9 can swap in these richer levels without reshaping upstream data contracts.

### Artifact and validation surface
- **D-10:** Materialize profile outputs as deterministic parquet artifacts for each profile family plus a row-aligned enriched dataset, following the same CLI-driven rebuild pattern used in Phases 2 through 6.
- **D-11:** Produce manual validation exports that let the user compare selected sessions against external profile charts, with separate visibility into overnight value area, daily profile levels, HTF balance edges, and detected LVNs for each validation date.
- **D-12:** Preserve Phase 3 compatibility during the transition by keeping explicit prior-day structural columns available in the enriched Phase 7 output while adding the richer overnight/HTF references as new columns instead of replacing the baseline contract silently.

### the agent's Discretion
- Exact smoothing kernel and prominence thresholds for LVN detection, provided they remain deterministic, documented, and testable.
- Precise artifact filenames and module boundaries for histogram builders, composite-profile assembly, and validation-export helpers.
- Additional helper columns that improve auditability, such as profile bucket counts, source-session coverage, or composite window metadata.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 7 goal, dependency boundary, and success criteria for daily/HTF profiles, LVNs, balance areas, and overnight value area.
- `.planning/REQUIREMENTS.md` - `STRC-02` through `STRC-06` define the required overnight value area, daily histogram, HTF composite, LVN, and balance-area outputs.
- `.planning/PROJECT.md` - Project-level data semantics, NQ tick specification, and the strategy framing that Phase 7 structural levels must support.
- `.planning/STATE.md` - Current project state showing Phase 7 as the active phase after Phase 6 completion.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked decisions for `trading_date`, ET session labels, and canonical parquet cache structure.
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md` - Locked expectations around strict causality, row-aligned artifacts, and deterministic validation surfaces.
- `.planning/phases/03-simple-structural-levels/03-CONTEXT.md` - Existing value-area definitions, prior-day structural contracts, and compatibility expectations that Phase 7 should extend rather than contradict.

### Existing implementation surfaces
- `src/vwap_revert/data_pipeline/cache.py` - Canonical parquet reload surface that Phase 7 should reuse as its input boundary.
- `src/vwap_revert/data_pipeline/sessions.py` - Session-label semantics for `overnight`, `rth`, and `trading_date` that must anchor profile windows.
- `src/vwap_revert/indicators/structural_levels.py` - Existing deterministic `POC` and value-area logic plus row-aligned structural output patterns to preserve or extend.
- `src/vwap_revert/cli.py` - Established phase-command and artifact rebuild pattern for adding a Phase 7 command.

### External specs
- No external specs - requirements are fully captured in decisions above and the planning documents listed here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/data_pipeline/cache.py`: `scan_canonical_cache()` already provides the lazy Phase 1 reload surface that Phase 7 can consume directly.
- `src/vwap_revert/data_pipeline/sessions.py`: session labeling already encodes the overnight and RTH boundaries needed for daily and overnight profile windows.
- `src/vwap_revert/indicators/structural_levels.py`: the Phase 3 module already implements deterministic profile aggregation, `POC` tie breaks, value-area expansion, and row-aligned structural attachment that can seed the richer Phase 7 engine.
- `src/vwap_revert/cli.py`: the CLI already follows a one-command-per-phase rebuild pattern with validation-date arguments and deterministic artifact output roots.

### Established Patterns
- The codebase is Polars-first, phase-scoped, and artifact-oriented; profile generation should prefer deterministic rebuilds over cached mutable state.
- Earlier phases separate reusable numeric artifacts from validation exports, so Phase 7 should preserve that split for daily, overnight, and HTF profile outputs.
- Prior phases favor explicit quality/status columns and stable column names for downstream reuse; Phase 7 should extend those contracts rather than introducing opaque nested blobs.

### Integration Points
- Phase 7 should read from the Phase 1 canonical cache, extend the existing structural-level pipeline, and write outputs consumable by later setup-detection and strategy-integration work.
- The enriched Phase 7 dataset is the future structural input for Phase 9 confluence scoring and multi-target execution logic, while still remaining compatible with the simpler Phase 4/5/6 contracts during the transition.
- Validation artifacts should live alongside other phase outputs so manual profile-chart checks remain part of the repo audit trail.

</code_context>

<specifics>
## Specific Ideas

- [auto] Selected all gray areas: profile session scope, profile construction defaults, HTF composite outputs, and artifact shape.
- [auto] Profile session scope -> Use completed overnight, prior-day RTH, and prior-only HTF references because they are the richest structural set that still stays fully causal at the RTH open.
- [auto] Price bucketing and value-area defaults -> Keep one-tick buckets and the existing Phase 3 deterministic value-area rules so new profile families stay consistent with prior structural outputs.
- [auto] HTF structure -> Use a deterministic rolling 180-day RTH composite with exposed HTF `POC`/value-area edges/LVNs because that directly matches the roadmap goal without introducing same-day leakage.
- [auto] Artifact shape -> Emit both per-profile parquet artifacts and a row-aligned enriched dataset so later phases can consume richer structural features without custom joins.

</specifics>

<deferred>
## Deferred Ideas

- Developing same-session RTH volume-profile features belong to a later enhancement once the baseline completed-session structural engine is in place.
- Regime-aware structural thresholds and weekly/monthly VWAP confluence remain Phase 8 work.
- Continuation-failure logic and confluence-driven entry scoring remain Phase 9 work.

</deferred>

---

*Phase: 07-volume-profile-engine*
*Context gathered: 2026-04-02*
