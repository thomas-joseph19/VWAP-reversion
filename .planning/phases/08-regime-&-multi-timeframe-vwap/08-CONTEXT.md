# Phase 8: Regime & Multi-Timeframe VWAP - Context

**Gathered:** 2026-04-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Add the Phase 8 enrichment layer that classifies each trading session into a causal volatility regime and computes reusable weekly and monthly VWAP anchors for downstream setup, target, and analytics work. This phase extends the existing row-aligned indicator pipeline; continuation-failure logic, confluence scoring, multi-target trade management, and regime/sigma/time-of-day performance decomposition remain out of scope for later phases.

</domain>

<decisions>
## Implementation Decisions

### Regime classification contract
- **D-01:** Compute one realized-volatility summary per completed trading session from the canonical front-month dataset, using the existing `trading_date` order and only data available at or before that session close so later sessions can consume the value without look-ahead bias.
- **D-02:** Classify each active trading date causally from a rolling history of prior completed sessions rather than from same-day full-session volatility, so the label is already known when Phase 4/5 logic evaluates the early RTH window.
- **D-03:** Keep the initial regime model strictly binary and explicit: higher-volatility sessions map to `short_gamma`, lower-volatility sessions map to `long_gamma`, and the raw realized-volatility statistic plus threshold metadata should remain available for auditability.
- **D-04:** Use a deterministic rolling threshold rule instead of a hand-maintained calendar of regime dates, and treat insufficient lookback history as an explicit quality state rather than silently fabricating a regime label.

### Weekly and monthly VWAP semantics
- **D-05:** Reuse the Phase 2 daily-VWAP input policy for higher-timeframe anchors: RTH trade rows only, `price * size` weighting, no synthetic mid-price volume, and forward-filled row alignment within each trading date once the first eligible anchor trade exists.
- **D-06:** Reset weekly VWAP at the first eligible RTH trade of each ET trading week and monthly VWAP at the first eligible RTH trade of each ET calendar month, keyed from the existing Phase 1 `trading_date` semantics instead of re-deriving calendar logic inside a separate pipeline.
- **D-07:** Preserve strict causality for the higher-timeframe anchors exactly as in Phase 2: each row's weekly/monthly VWAP may only use trades at or before that row timestamp, and pre-anchor rows remain null rather than backfilled.
- **D-08:** Handle contract-roll discontinuities in weekly and monthly VWAP the same way Phase 7 handled HTF structural composites: align prior trade prices onto the active contract axis with deterministic completed-session roll deltas so anchors stay comparable across rolls instead of breaking at quarter boundaries.

### Output surface and downstream integration
- **D-09:** Materialize Phase 8 as a reusable row-aligned enriched parquet that appends regime columns and weekly/monthly VWAP columns onto the canonical timeseries without mutating upstream Phase 2 or Phase 7 artifacts in place.
- **D-10:** Also emit a compact session-level artifact that records per-session realized-volatility values, threshold inputs, final regime labels, and any quality/status fields so regime classification can be reviewed independently of the row-level dataset.
- **D-11:** Backfill the existing placeholder `regime_label` and `regime_reason` fields used by Phase 4/5/6 contracts, keeping column names stable so setup detection, simulation, and analytics can consume Phase 8 outputs without schema churn.
- **D-12:** Produce deterministic validation exports for selected dates that expose timestamped weekly/monthly VWAP values plus the session-level regime decision inputs, enabling manual chart comparison and spot-checks against the author's expected short-vs-long-gamma behavior.

### the agent's Discretion
- The exact realized-volatility formula and rolling lookback length, as long as the method is causal, documented, and stable enough for downstream research and validation.
- The precise thresholding mechanic for mapping realized volatility into binary `short_gamma` / `long_gamma` labels, as long as it stays deterministic and exposes enough metadata for auditability.
- Additional helper columns such as weekly/monthly anchor identifiers, regime percentile, or lookback coverage counts when they improve debugging without changing the Phase 8 contract.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 8 goal, dependency boundary, and success criteria for realized-volatility regime classification plus weekly/monthly VWAP anchors.
- `.planning/REQUIREMENTS.md` - `REGM-01`, `REGM-02`, `REGM-03`, `VWAP-04`, and `VWAP-05` define the Phase 8 deliverables.
- `.planning/PROJECT.md` - Project-level strategy framing, NQ contract constraints, and the realized-volatility proxy rationale for gamma regime classification.
- `.planning/STATE.md` - Current milestone state showing Phase 8 as the active focus after Phase 7 verification.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked `trading_date`, session-label, canonical-cache, and roll-map decisions that Phase 8 must inherit.
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md` - Locked RTH-only VWAP semantics, forward-fill behavior, and strict causality rules that weekly/monthly anchors should extend.
- `.planning/phases/04-setup-detection/04-CONTEXT.md` - Locked placeholder `regime_label` / `regime_reason` schema expectations and setup-window semantics that Phase 8 will enrich rather than redesign.
- `.planning/phases/06-core-analytics-output/06-CONTEXT.md` - Locked analytics-schema expectations showing regime fields are already carried downstream for later decomposition.
- `.planning/phases/07-volume-profile-engine/07-CONTEXT.md` - Locked roll-bridging approach and row-aligned artifact pattern that should guide higher-timeframe anchor handling across contract rolls.
- `.planning/phases/07-volume-profile-engine/07-VERIFICATION.md` - Verified Phase 7 roll-bridged HTF behavior, which is the closest existing precedent for Phase 8 roll handling.

### Existing implementation surfaces
- `src/vwap_revert/indicators/vwap.py` - Existing cumulative VWAP implementation, null-before-anchor behavior, band-column conventions, and validation-artifact pattern to extend for weekly/monthly anchors.
- `src/vwap_revert/data_pipeline/cache.py` - Canonical cache reload surface that Phase 8 should use as its input boundary.
- `src/vwap_revert/data_pipeline/sessions.py` - Existing ET-local timestamp and `trading_date` semantics that should define weekly/monthly reset boundaries.
- `src/vwap_revert/indicators/setup_detection.py` - Current placeholder regime fields and downstream setup-log contract that Phase 8 must keep compatible.
- `src/vwap_revert/simulation.py` - Existing trade-log fields and Phase 5 schema that already carry `regime_label` / `regime_reason`.
- `src/vwap_revert/analytics.py` - Existing analytics export path that preserves regime context for later segmentation.
- `src/vwap_revert/cli.py` - Established phase-builder command pattern and deterministic output-root wiring for new Phase 8 commands.

### External specs
- No external specs - requirements are fully captured in the planning documents and prior-phase context listed above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/indicators/vwap.py`: already implements the cumulative trade-only VWAP pattern, anchor null policy, and artifact-writing style that Phase 8 can reuse for weekly/monthly anchors.
- `src/vwap_revert/data_pipeline/cache.py`: already exposes the canonical parquet reload surface, so Phase 8 can stay rebuildable from one trusted dataset.
- `src/vwap_revert/data_pipeline/sessions.py`: already defines the ET-local timestamps and trading-date semantics needed for causal session bucketing.
- `src/vwap_revert/indicators/setup_detection.py`, `src/vwap_revert/simulation.py`, and `src/vwap_revert/analytics.py`: already carry regime placeholder columns through the downstream pipeline, which Phase 8 can begin populating without changing file contracts.
- `src/vwap_revert/cli.py`: already follows the one-command-per-phase rebuild pattern with validation-date arguments and phase-scoped output roots.

### Established Patterns
- The repo is Polars-first, deterministic, and row-aligned: new indicator layers enrich the canonical dataframe and write explicit artifacts rather than mutating hidden state.
- Prior phases favor causal transforms with explicit quality columns over silent fallbacks when upstream history is insufficient.
- Roll-sensitive higher-timeframe logic is handled by deterministic bridge metadata rather than by nulling whole windows or backfilling arbitrary substitutes.

### Integration Points
- Phase 8 should load from the Phase 1 canonical cache, derive session-level regime metadata, compute weekly/monthly VWAP columns, and write outputs that can directly feed later setup, simulation, and analytics work.
- The row-level Phase 8 enriched artifact is the natural bridge into Phase 9, where continuation-failure logic, confluence scoring, and multi-target exits will need regime and higher-timeframe VWAP context on every row.
- Validation exports should live alongside the new Phase 8 artifacts so manual chart comparisons and regime spot-checks remain part of the repo audit trail.

</code_context>

<specifics>
## Specific Ideas

- [auto] Selected all gray areas: regime classification policy, higher-timeframe VWAP semantics, and artifact shape.
- [auto] Regime policy -> classify each active session from prior completed-session realized volatility so the label is causal for the 9:30-11:30 ET setup window.
- [auto] VWAP policy -> extend the existing Phase 2 RTH-only trade-weighted VWAP logic to weekly and monthly anchors instead of introducing a second anchor methodology.
- [auto] Roll handling -> reuse the Phase 7 roll-bridging idea for weekly/monthly anchors so higher-timeframe VWAPs remain continuous across quarterly contract changes.
- [auto] Artifact shape -> emit both a row-level enriched parquet and a session-level regime summary so downstream strategy code and manual validation can each consume the most natural surface.

</specifics>

<deferred>
## Deferred Ideas

- Regime-adjusted setup thresholds and selectivity tuning are consumed in later execution logic, not defined fully inside the baseline Phase 8 context capture.
- Continuation-failure detection, confluence scoring, and multi-target execution remain Phase 9 work.
- Regime/sigma/time-of-day breakdowns, equity-curve export, and comparison against the author's reference statistics remain Phase 10 work.

</deferred>

---

*Phase: 08-regime-&-multi-timeframe-vwap*
*Context gathered: 2026-04-03*
