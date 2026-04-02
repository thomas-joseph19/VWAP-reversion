# Phase 4: Setup Detection - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Identify candidate VWAP reversion setups by combining the Phase 2 daily VWAP extension state with the Phase 3 structural-level proximity state during the early regular trading hours window. This phase ends at setup detection and setup logging; continuation-failure confirmation, trade entry/exit logic, and analytics remain out of scope for later phases.

</domain>

<decisions>
## Implementation Decisions

### Trading-window gating
- **D-01:** Evaluate setup eligibility only on rows whose `ts_recv_et` falls inside a configurable RTH window, defaulting to `09:30:00` through `11:30:00` America/New_York on the row's existing `trading_date`.
- **D-02:** Reuse the Phase 1 session labels and Phase 2/3 row-aligned datasets rather than rebuilding calendars or sessions inside the setup detector.
- **D-03:** Treat rows outside the configured window as definitively ineligible, but preserve explicit boolean columns showing whether the row passed the time-window filter so downstream phases can audit why a candidate was or was not emitted.

### VWAP-extension semantics
- **D-04:** Detect extension from the current row's actionable price relative to the Phase 2 `daily_vwap` and `daily_sigma`, computing a signed sigma-distance feature so later phases can distinguish above-VWAP and below-VWAP setups.
- **D-05:** Use a configurable absolute sigma range with defaults `1.7` to `3.0`, interpreted inclusively at both bounds for the initial MVP detector.
- **D-06:** If `daily_vwap` or `daily_sigma` is null or `daily_sigma` is zero, mark the row as not extended instead of attempting fallback math or synthetic normalization.

### Structural confluence and candidate emission
- **D-07:** Require at least one active structural proximity hit from Phase 3 (`structural_levels_within_threshold >= 1`) for a row to qualify as a candidate setup.
- **D-08:** Emit candidate setups on the transition into a valid combined state rather than on every qualifying second, so the Phase 4 log captures one deterministic setup event per contiguous excursion episode and avoids flooding later trade-simulation phases with duplicate entries.
- **D-09:** Assign the candidate direction from the sign of the signed sigma-distance: positive extension implies a short reversion candidate, negative extension implies a long reversion candidate.

### Output artifacts and logged context
- **D-10:** Materialize both a row-aligned enriched parquet with setup flags/features and a compact setup-log artifact containing one row per emitted candidate.
- **D-11:** Log every emitted setup with timestamp, trading date, actionable price, `daily_vwap`, `daily_sigma`, signed sigma distance, nearest structural level, nearest structural distance, structural hit count, bid/ask when available, and placeholder regime fields that remain null until Phase 8.
- **D-12:** Keep column names explicit and machine-friendly so the same Phase 4 artifacts can feed Phase 5 trade simulation and later analytics without reshaping.

### the agent's Discretion
- Exact helper boundaries for row enrichment versus setup-log extraction.
- Whether the compact setup log is emitted as parquet only or parquet plus a lightweight CSV preview, as long as it stays deterministic.
- Additional diagnostic columns that improve auditability without changing the core setup definition.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 4 goal, dependencies, requirements, and success criteria for time-window filtering plus combined setup detection.
- `.planning/REQUIREMENTS.md` - `VWAP-03`, `SGNL-01`, `SGNL-02`, and `SGNL-03` define the extension threshold, trading-window filter, combined predicate, and setup-log fields.
- `.planning/PROJECT.md` - Project-level strategy framing confirms that the edge is being measured during the first 1-2 hours of the NY session around VWAP and structural levels.
- `.planning/STATE.md` - Current milestone state and deferred validation debt that Phase 4 must carry forward without blocking local progress.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked timestamp, session-label, trading-date, and canonical-cache decisions that Phase 4 must inherit.
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md` - Locked VWAP-anchor, sigma-band, causality, and artifact-shape decisions that define the extension surface.
- `.planning/phases/03-simple-structural-levels/03-CONTEXT.md` - Locked structural-level, proximity-threshold, and artifact-shape decisions that define the confluence surface.

### Existing implementation surfaces
- `src/vwap_revert/cli.py` - Existing phase-command CLI pattern and artifact-emission structure that Phase 4 should extend.
- `src/vwap_revert/indicators/vwap.py` - Current row-aligned VWAP enrichment surface and validation-artifact pattern that Phase 4 will consume.
- `src/vwap_revert/indicators/structural_levels.py` - Current row-aligned structural enrichment surface, proximity features, and artifact-writing conventions that Phase 4 will consume.
- `tests/indicators/test_vwap.py` - Existing indicator-test style and fixtures for Phase 2-derived signals.
- `tests/indicators/test_structural_levels.py` - Existing indicator-test style and fixtures for Phase 3-derived signals.

### External specs
- No external specs - requirements are fully captured in the planning documents and prior-phase context listed above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/indicators/vwap.py`: already computes row-aligned `daily_vwap`, `daily_sigma`, and 1-4 sigma bands needed to derive extension state.
- `src/vwap_revert/indicators/structural_levels.py`: already computes nearest-level metadata, per-level distances, and inclusive structural-threshold flags needed to derive confluence.
- `src/vwap_revert/cli.py`: already establishes the phase-command pattern for deterministic artifact builders with validation-date and output-root arguments.

### Established Patterns
- Earlier phases build deterministic parquet artifacts plus validation metadata instead of hidden in-memory steps.
- Indicator layers are row-aligned to the canonical cache and favor explicit numeric features over presentation-only summaries.
- The codebase preserves strict causality and carries forward nulls/quality signals instead of backfilling synthetic market state.

### Integration Points
- Phase 4 should start from the canonical cache, append Phase 2 VWAP features and Phase 3 structural features, then derive setup-detection columns without recomputing upstream indicators.
- The emitted setup log becomes the direct handoff surface for Phase 5 trade simulation and the future trade-entry rules.
- Phase 4 should wire a new CLI command alongside the existing phase builders so local rebuilds stay consistent with the earlier phases.

</code_context>

<specifics>
## Specific Ideas

- Auto-selected default: treat Phase 4 as a deterministic event-detector that emits one setup when the combined predicate first becomes true, rather than logging every second in a qualifying stretch.
- Auto-selected default: preserve a signed sigma-distance feature and a directional setup label now, because both are likely to matter in Phase 5 entry logic and later analytics.
- Auto-selected default: carry a nullable regime field through the setup log now so the artifact schema is already ready for Phase 8 enrichment without needing a breaking schema change later.

</specifics>

<deferred>
## Deferred Ideas

- Mechanical continuation-failure confirmation belongs to Phase 9, not Phase 4.
- Gamma-regime-aware thresholds belong to Phase 8 once realized-volatility classification exists.
- Multi-structural confluence scoring and advanced ranking belong to later strategy-integration work, not the MVP detector.

</deferred>

---

*Phase: 04-setup-detection*
*Context gathered: 2026-04-02*
