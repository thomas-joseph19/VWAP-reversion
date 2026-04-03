# Phase 5: Trade Simulation Engine - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Simulate mechanical trades from the Phase 4 setup log so the project can measure whether the detected VWAP-reversion setups produce positive expectancy under a simple, reproducible execution model. This phase covers entry, exit, stop-loss, commissions, one-position-at-a-time rules, and session-end forced liquidation. Multi-target exits, regime-aware trade management, and continuation-failure refinement remain out of scope for later phases.

</domain>

<decisions>
## Implementation Decisions

### Entry semantics
- **D-01:** Enter immediately when a Phase 4 setup event is emitted; Phase 5 does not wait for any extra continuation-failure confirmation.
- **D-02:** Use the Phase 4 setup direction as the trade direction directly: positive sigma extension produces a short reversion trade, and negative sigma extension produces a long reversion trade.
- **D-03:** Treat the setup log as the canonical trade-trigger surface for this MVP phase rather than re-deriving setup conditions inside the simulator.

### Fill and friction model
- **D-04:** Model fills from the contemporaneous BBO side without adding extra slippage: long entries and short exits use the ask, while short entries and long exits use the bid when quotes are available.
- **D-05:** Additional slippage defaults to zero because the intended environment is a simulated prop-firm-style evaluation rather than live market execution.
- **D-06:** Round-trip commissions remain in scope and should be configurable, with a realistic NQ default rate chosen during planning.

### Exit and stop policy
- **D-07:** The primary profit target is full reversion to the current daily VWAP, matching the roadmap's baseline Phase 5 success criterion.
- **D-08:** Use a configurable fixed stop-loss threshold in absolute NQ points for the MVP baseline, evaluated from maximum adverse excursion after entry.
- **D-09:** The default stop should be treated as a planning-time baseline rather than an optimized parameter, because the most profitable threshold cannot be known honestly before backtest results exist.

### Position management
- **D-10:** Only one live position may be open at a time across the entire strategy.
- **D-11:** If a new setup appears while a trade is active, skip it entirely instead of queuing, netting, or pyramiding.
- **D-12:** Force-close any still-open trade at the session-end cutoff defined by the roadmap, even if neither the VWAP target nor the stop-loss has been hit.

### the agent's Discretion
- Exact commission default, as long as it is realistic for NQ and configurable.
- The initial fixed stop distance, as long as it is documented as a non-optimized baseline for later analysis.
- Exact artifact schema for trade-level diagnostics beyond the required entry/exit/P&L fields.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning and acceptance
- `.planning/ROADMAP.md` - Phase 5 goal, dependencies, and success criteria for immediate setup-driven trade simulation, costs, stops, one-position rules, and session-end exits.
- `.planning/REQUIREMENTS.md` - `TSIM-01`, `TSIM-02`, `TSIM-03`, `TSIM-04`, `TSIM-05`, `TSIM-07`, and `TSIM-08` define the required simulation behaviors.
- `.planning/PROJECT.md` - Project-level strategy framing, NQ contract specs, and the model objective of testing VWAP reversion setups mechanically.
- `.planning/STATE.md` - Current project state and carried validation debt from earlier phases.

### Prior phase context
- `.planning/phases/01-data-pipeline-foundation/01-CONTEXT.md` - Locked dataset, timestamp, session-label, and canonical-cache decisions that Phase 5 must inherit.
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md` - Locked daily VWAP semantics that define the primary reversion target.
- `.planning/phases/03-simple-structural-levels/03-CONTEXT.md` - Locked structural-level decisions that shaped the setup context carried into the trade log.
- `.planning/phases/04-setup-detection/04-CONTEXT.md` - Locked setup-event semantics, direction assignment, bid/ask logging, and artifact shape that Phase 5 must consume directly.

### Research guidance
- `.planning/research/SUMMARY.md` - MVP rationale, cautions around execution realism, and the recommended minimal backtest sequence.
- `.planning/research/PITFALLS.md` - Known fill-model and optimization traps that planning should avoid.
- `.planning/research/FEATURES.md` - Trade-simulation feature framing, especially the MVP distinction between simple baseline exits and later multi-target logic.
- `.planning/research/ARCHITECTURE.md` - Proposed pipeline boundary for trade simulation, target handling, stop logic, and position tracking.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/vwap_revert/indicators/setup_detection.py`: already emits deterministic setup events with direction, sigma-distance, structural metadata, and bid/ask context.
- `src/vwap_revert/indicators/vwap.py`: already defines the daily VWAP fields that Phase 5 should target without recomputing indicator state.
- `src/vwap_revert/cli.py`: already establishes the phase-builder command pattern for deterministic rebuilds and artifact emission.

### Established Patterns
- Earlier phases favor row-aligned artifacts, explicit parquet outputs, and deterministic rebuild commands over hidden in-memory workflows.
- The project keeps strict causality and forwards explicit nulls/quality signals instead of inventing synthetic market state.
- Current phases separate signal generation from downstream consumption, so Phase 5 should read the setup log rather than collapse Phase 4 and Phase 5 into one monolith.

### Integration Points
- Phase 5 should consume the Phase 4 compact setup log as the entry-trigger surface and the enriched row-level dataset or canonical cache as the path for post-entry state evaluation.
- The resulting trade log becomes the direct input for Phase 6 analytics.
- Position-management and fill-policy outputs should be shaped so later Phase 9 logic can add richer confirmation and targets without breaking the baseline trade schema.

</code_context>

<specifics>
## Specific Ideas

- User direction: follow the model to the best available approximation in the current repo, but do not add extra slippage because the target environment is a simulated prop-firm evaluation.
- User direction: enforce exactly one live position at a time.
- User direction: enter immediately on the setup event instead of waiting for a later confirmation rule.
- Since "most profitable" cannot be known before backtesting, planning should choose a robust fixed-stop baseline and treat it as a configurable research parameter rather than a claimed optimum.

</specifics>

<deferred>
## Deferred Ideas

- Continuation-failure refinement belongs to Phase 9, not this MVP simulation phase.
- Multi-target exits such as weekly VWAP or developing POC belong to later phases.
- Slippage sensitivity sweeps and richer live-execution realism can be added later if needed, but they are not the baseline requested here.

</deferred>

---

*Phase: 05-trade-simulation-engine*
*Context gathered: 2026-04-02*
