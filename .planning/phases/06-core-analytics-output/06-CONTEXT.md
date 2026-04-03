# Phase 6: Core Analytics & Output - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the completed Phase 5 trade-simulation outputs into Phase 6 analytics artifacts that quantify strategy performance. This phase covers trade-log completion for downstream analysis, computation of the roadmap's core performance metrics, and structured CSV/JSON exports. Regime decomposition beyond the carried fields, advanced bucketing, equity-curve studies beyond max drawdown, and multi-target strategy comparisons remain out of scope for later phases.

</domain>

<decisions>
## Implementation Decisions

### Analytics input contract
- **D-01:** Treat the Phase 5 trade log parquet as the canonical input for Phase 6 analytics rather than replaying trades again or recomputing Phase 4/5 logic inside the analytics layer.
- **D-02:** Preserve one row per completed trade and keep the Phase 5 context columns (`setup_sigma_signed`, `nearest_structural_level`, `regime_label`, `regime_reason`) in the analytics-ready trade log so later phases can segment results without schema churn.
- **D-03:** Fill the roadmap-required trade-log fields by deriving missing analysis columns from existing Phase 5 economics, especially converting point P&L into ticks while retaining net dollar P&L as the primary cost-aware measure.

### Metric definitions
- **D-04:** Compute the baseline performance metrics from completed trades only: win rate, average win/loss ratio, profit factor, max drawdown, Sharpe ratio, and total P&L.
- **D-05:** Use `net_dollars` as the default economic basis for aggregate performance metrics so commissions remain included, while also surfacing point/tick-level trade fields for inspection.
- **D-06:** Keep metric formulas deterministic and explicit, including documented handling for edge cases such as zero losses, zero variance, or too few trades for a stable Sharpe estimate.

### Output surfaces
- **D-07:** Emit both machine-readable summary artifacts and analyst-friendly tabular exports from the same Phase 5 input snapshot so CSV and JSON stay numerically aligned.
- **D-08:** Export the enriched trade log to CSV for spreadsheet-style review and export aggregate metrics to JSON for downstream scripting, while allowing additional companion files if they improve auditability.
- **D-09:** Follow the established per-phase artifact pattern: deterministic filenames, explicit manifests/metadata where useful, and validation exports keyed by selected dates or runs instead of ad hoc notebook-only analysis.

### CLI and workflow integration
- **D-10:** Add a dedicated Phase 6 builder command alongside the existing phase commands instead of hiding analytics behind a test helper or notebook-only path.
- **D-11:** Phase 6 should consume Phase 5 output directories directly, produce a self-contained analytics output directory, and avoid mutating upstream artifacts in place.
- **D-12:** Keep the analytics schema Phase 9/10-friendly by exposing enough trade-level detail now that future regime, sigma-band, and time-of-day breakdowns can layer on without reworking the baseline exports.

### the agent's Discretion
- Exact file names for the Phase 6 CSV/JSON artifacts, as long as they are deterministic and clearly phase-scoped.
- Precise Sharpe scaling convention and null policy, as long as it is documented and consistent.
- Additional summary metrics or diagnostics beyond the roadmap minimum, as long as they do not distract from the required Phase 6 contract.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 6 goal, dependency on Phase 5, and success criteria for trade-log completion, core metrics, and CSV/JSON outputs.
- `.planning/REQUIREMENTS.md` - `ANLY-01`, `ANLY-02`, and `ANLY-03` define the required trade-log fields, baseline metrics, and structured export formats.
- `.planning/PROJECT.md` - Project-level research objective, NQ contract specs, and backtest-output constraints for a file-based analytics workflow.
- `.planning/STATE.md` - Current project state, deferred validation debt, and the handoff from Phase 5 into analytics planning.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked canonical-cache, timestamp, and artifact-shape decisions that continue to constrain downstream outputs.
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md` - Locked VWAP semantics that define the Phase 5 target behavior reflected in analytics.
- `.planning/phases/03-simple-structural-levels/03-CONTEXT.md` - Locked structural-level semantics whose labels and distances are carried into trade-level outputs.
- `.planning/phases/04-setup-detection/04-CONTEXT.md` - Locked setup-event and context-column semantics that Phase 5 passed into the trade log.
- `.planning/phases/05-trade-simulation-engine/05-CONTEXT.md` - Locked fill, commission, stop, overlap, and session-exit assumptions that define the economics of the analytics input.
- `.planning/phases/05-trade-simulation-engine/05-VERIFICATION.md` - Verified Phase 5 behavior and confirms the trade-log contract feeding Phase 6.
- `.planning/phases/05-trade-simulation-engine/05-HUMAN-UAT.md` - Recorded completion of the human commission-baseline review that unblocks Phase 6 planning.

### Existing implementation surfaces
- `src/vwap_revert/simulation.py` - Current trade-log schema, validation export columns, and artifact-writing behavior that Phase 6 should consume rather than duplicate.
- `src/vwap_revert/cli.py` - Existing phase-builder command pattern and CLI argument conventions that Phase 6 should extend.
- `tests/indicators/test_trade_simulation_validation.py` - Existing artifact-validation style and fixture setup that can guide Phase 6 analytics-output tests.

### External specs
- No external specs - requirements are fully captured in the planning documents and prior-phase context listed above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/simulation.py`: already writes deterministic Phase 5 trade-log parquet, skipped-setup parquet, validation CSV, and manifest metadata with stable economics fields.
- `src/vwap_revert/cli.py`: already provides the per-phase builder-command pattern, validation-date parsing helpers, and phase-scoped output-root wiring.
- `tests/indicators/test_trade_simulation_validation.py`: already demonstrates the repo's preferred pattern for fixture-driven artifact validation at the CLI boundary.

### Established Patterns
- The project favors deterministic parquet plus validation/report artifacts over notebook-only or interactive-only analysis.
- Phase builders consume the previous phase's output directory and write a new self-contained output directory with explicit file names.
- Validation exports are intentionally small, date-targeted, and easy to inspect manually, while manifests document artifact contracts and key assumptions.

### Integration Points
- Phase 6 should start from the Phase 5 trade-log artifact and derived validation/manifest metadata rather than reaching back to Phase 4 setup rows.
- The new analytics output directory should be wired as the direct input surface for later Phase 9/10 decomposition work.
- CLI, tests, and artifact schemas should stay aligned so future planning can add deeper breakdowns without changing the baseline export contract.

</code_context>

<specifics>
## Specific Ideas

- Auto-selected default: use the Phase 5 trade log as the sole truth source for Phase 6 metrics so analytics cannot drift from the executed replay rules.
- Auto-selected default: keep `net_dollars` as the headline performance basis because it already includes round-trip commissions, while also deriving tick-based trade fields to satisfy the roadmap trade-log requirement.
- Auto-selected default: separate trade-level exports from aggregate metrics outputs so analysts can inspect individual trades in CSV while scripts consume summary JSON directly.

</specifics>

<deferred>
## Deferred Ideas

- Regime, sigma-band, and time-of-day breakdowns belong to Phase 10, not the baseline Phase 6 metrics pass.
- Weekly VWAP, monthly VWAP, and developing POC target comparisons belong to later phases once those anchors exist.
- Continuation-failure refinements and multi-target management remain Phase 9 work, not analytics responsibilities.

</deferred>

---

*Phase: 06-core-analytics-output*
*Context gathered: 2026-04-02*
