# Phase 3: Simple Structural Levels - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Compute prior-day `VAH`, `VAL`, and `POC` from the Phase 1 canonical NQ dataset and expose row-aligned structural-level proximity signals that later phases can combine with VWAP extension during the early RTH trading window. Full daily/HTF volume-profile features, overnight value area, LVNs, and balance-area analytics remain out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Session scope and source data
- **D-01:** Build prior-day value area levels from the prior completed RTH session only, not the full 24-hour session, so the structural references align with the strategy's RTH-only execution model and Phase 2's RTH-anchored VWAP baseline.
- **D-02:** Derive the prior-day profile from trade-bearing observations available in the 1-second BBO dataset, using actual traded volume distribution where Phase 1/2 data semantics identify trade prints; quote-only rows must not contribute synthetic volume to the value area.
- **D-03:** Treat the prior session as the most recent completed RTH session on the previous `trading_date`; if that session is missing or unusable, emit null structural levels plus explicit quality metadata instead of silently substituting another day.

### Profile construction and level definition
- **D-04:** Compute the prior-day profile on native traded price levels from the 1-second dataset rather than introducing wider custom buckets, preserving maximum information for future machine-learning feature extraction and avoiding irreversible aggregation choices in the baseline artifact.
- **D-05:** Define `POC` as the price level with the highest traded volume in the prior RTH session; when multiple prices tie, break ties deterministically by choosing the price closest to the session's volume-weighted fair-value center and then the lower price if still tied.
- **D-06:** Define `VAH` and `VAL` using a deterministic 70% value-area expansion around `POC`, expanding to the adjacent price level with greater incremental volume at each step and using a stable tie-break rule so outputs are reproducible and audit-friendly.

### Output shape and proximity features
- **D-07:** Publish a compact per-session structural-level artifact keyed by `trading_date` and also a row-aligned enriched dataset that forward-carries the active prior-day `VAH`, `VAL`, and `POC` onto each current-session row, matching the Phase 2 pattern of reusable downstream columns.
- **D-08:** Compute proximity using the current row's best available actionable price from the BBO dataset, with a configurable absolute distance threshold defaulting to `10.0` NQ points and an inclusive comparison (`<= threshold`).
- **D-09:** Emit machine-learning-friendly proximity features in addition to boolean flags: signed distance to each level, nearest-level label, nearest-level distance, and a count of how many structural levels fall within threshold on that row.

### Validation and downstream compatibility
- **D-10:** Restrict the baseline validation target to prior-day RTH value area levels that can be checked against a reference volume-profile chart; overnight value area validation is explicitly deferred to Phase 7.
- **D-11:** Preserve strict causality: a row on trading date `T` may only see structural levels computed from completed sessions before that row's RTH activity, never same-session developing profile information.
- **D-12:** Shape artifacts and column names for direct use by later setup-detection and analytics phases, favoring explicit numeric features over presentation-only summaries so the same outputs can feed both rule-based signals and later ML feature engineering.

### the agent's Discretion
- Exact helper/module boundaries for profile construction, artifact writing, and proximity enrichment.
- The precise fair-value-center metric used for `POC` tie-breaking, as long as it is deterministic and documented.
- Additional quality/reporting columns that make missing prior-session inputs easier to audit.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 3 goal, dependency boundary, and success criteria for prior-day `VAH`/`VAL`/`POC` plus proximity detection.
- `.planning/REQUIREMENTS.md` - `STRC-01` and `STRC-07` define the required value-area outputs and configurable proximity detection behavior.
- `.planning/PROJECT.md` - Project-level strategy framing confirms RTH-focused execution and future ML work is deferred but desirable to preserve in artifact design.
- `.planning/STATE.md` - Current project state marking Phase 3 as the active frontier after Phase 2 completion.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked decisions around ET-local timestamps, `trading_date`, session labels, and canonical parquet cache layout that Phase 3 must inherit.
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md` - Locked decisions around RTH-only strategy alignment, strict causality, row-aligned outputs, and artifact design that Phase 3 should match.

### Existing implementation surfaces
- `src/vwap_revert/cli.py` - Existing phase-command CLI pattern and artifact emission entrypoint conventions.
- `src/vwap_revert/data_pipeline/cache.py` - Canonical parquet scan/write surface that Phase 3 should reuse as its input boundary.

### External specs
- No external specs - requirements are fully captured in decisions above and the planning documents listed here.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/data_pipeline/cache.py`: `scan_canonical_cache()` provides the Phase 1 parquet reload surface that should feed structural-level computation.
- `src/vwap_revert/cli.py`: already exposes phase-specific subcommands (`build-phase1-cache`, `build-phase2-vwap`) and establishes the pattern for adding a Phase 3 command plus artifact output path arguments.
- `src/vwap_revert/indicators/vwap.py`: demonstrates the current row-aligned indicator-artifact pattern and validation-export style that Phase 3 can mirror for structural outputs.

### Established Patterns
- The codebase is Polars-first, artifact-oriented, and favors deterministic rebuilds over hidden state.
- Earlier phases preserve strict causality and explicit audit artifacts, so Phase 3 should avoid any developing-profile leakage or opaque aggregation.
- Phase 2 materialized reusable numeric columns for later phases; Phase 3 should do the same for structural distances and flags instead of emitting only human-readable reports.

### Integration Points
- Phase 3 should load the canonical Phase 1 cache, compute prior-session structural levels, and optionally enrich the same row set that Phase 2 uses for VWAP/band columns.
- The resulting structural features become a direct dependency for Phase 4 setup detection and an indirect dependency for trade simulation, analytics, and ML feature engineering.
- Validation outputs should sit alongside other phase artifacts so manual chart comparison remains part of the audit trail.

</code_context>

<specifics>
## Specific Ideas

- User direction: use the existing 1-second BBO dataset, prefer whatever is most robust in that environment, and optimize choices for future machine-learning use.
- Working assumption carried into this phase: the trading model only acts during RTH, especially the early `9:30-11:30 ET` window, so prior-day structural references should be anchored to RTH behavior unless a later phase explicitly broadens scope.
- Preserve rich numeric features now, even if the immediate strategy only needs boolean proximity, so later ML/optimization work can reuse the same structural artifact without recomputing the profile baseline.

</specifics>

<deferred>
## Deferred Ideas

- Overnight value area (`STRC-02`) and other Globex-derived structural references belong to Phase 7, not this baseline phase.
- LVNs, HTF balance extremes, and richer composite profile analytics belong to the later volume-profile phase.

</deferred>

---

*Phase: 03-simple-structural-levels*
*Context gathered: 2026-04-02*
