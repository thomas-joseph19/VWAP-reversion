---
phase: 05-trade-simulation-engine
plan: 02
subsystem: simulation
tags: [polars, pytest, replay, vwap, nq]
requires:
  - phase: 05-01
    provides: entry pricing, exit pricing, and trade-opening primitives
provides:
  - causal single-trade replay with executable-side target, stop, and session-end exits
  - batch trade simulation output contract with trade_log and skipped_setups frames
  - deterministic replay tests for long target, conservative same-row stop, and 16:00 ET liquidation
affects: [phase-06-analytics, trade-log-schema, position-management]
tech-stack:
  added: []
  patterns: [sequential setup replay, executable-side exit checks, conservative same-row stop precedence]
key-files:
  created: [.planning/phases/05-trade-simulation-engine/05-02-SUMMARY.md]
  modified: [src/vwap_revert/simulation.py, tests/indicators/test_trade_simulation.py]
key-decisions:
  - "Replay scans only same-session rows at or after entry_ts and raises if no 16:00 ET liquidation row exists."
  - "Stop-loss evaluation uses executable exit-side quotes and takes precedence over same-row VWAP hits."
patterns-established:
  - "Phase 5 replay logic returns a flat dict shaped for later DataFrame assembly."
  - "Batch outputs always include an explicit skipped_setups frame, even when empty."
requirements-completed: [TSIM-02, TSIM-07, TSIM-08]
duration: inline
completed: 2026-04-02
---

# Phase 05 Plan 02: Trade Simulation Replay Summary

**Causal VWAP replay with executable-side exits, conservative stop precedence, and a batch simulation contract for downstream trade analytics**

## Performance

- **Duration:** inline
- **Started:** 2026-04-02T22:49:03Z
- **Completed:** 2026-04-02T23:00:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added RED/GREEN replay coverage for executable-side VWAP targets, stop-loss MAE, and exact `16:00:00 ET` liquidation timing.
- Implemented `replay_single_trade` with causal row filtering, executable-side exit checks, explicit exit reasons, and post-trade economics.
- Added `SimulationBatchResult` and `simulate_trades` so later plans can consume a stable `trade_log` / `skipped_setups` contract.

## Task Commits

1. **Task 1: Add failing replay tests for VWAP target exits, stop-loss MAE, and 16:00 ET forced liquidation** - `3f436f1` (`test`)
2. **Task 2: Implement causal single-trade replay and batch trade simulation over setup events** - `7140e51` (`feat`)

## Files Created/Modified
- `src/vwap_revert/simulation.py` - Added causal replay, batch result contract, and batch simulation loop.
- `tests/indicators/test_trade_simulation.py` - Extended Phase 5 TDD coverage for replay exits while preserving the 05-01 pricing tests.
- `.planning/phases/05-trade-simulation-engine/05-02-SUMMARY.md` - Captures execution results for Plan 05-02.

## Decisions Made
- Used the executable exit side itself for both target detection and MAE tracking so stop/target checks match the actual fill model.
- Applied adverse-first precedence when stop and target are both true on one replay row.
- Kept `skipped_setups` present as an explicit DataFrame contract now, even though later plans will populate more skip reasons.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `python -m pytest` emitted cache warnings because this workspace cannot write `.pytest_cache`; test execution still completed successfully.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 now has a stable replay contract for one-trade-at-a-time batch simulation and later analytics.
- `simulate_trades` already emits `position_active` skips, so Plan 05-03 can extend skip handling without redesigning the output shape.

## Self-Check: PASSED

- Verified `.planning/phases/05-trade-simulation-engine/05-02-SUMMARY.md` exists.
- Verified task commits `3f436f1` and `7140e51` exist in git history.

---
*Phase: 05-trade-simulation-engine*
*Completed: 2026-04-02*
