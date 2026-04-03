---
phase: 07-volume-profile-engine
plan: 01
subsystem: indicators
tags: [polars, volume-profile, overnight, htf, lvn]
requires:
  - phase: 01-data-pipeline-foundation
    provides: canonical session labels, trading dates, and front-month symbols
  - phase: 03-simple-structural-levels
    provides: deterministic POC and value-area tie-break rules
provides:
  - completed-session overnight profile builder
  - completed-session daily RTH profile builder
  - prior-only HTF composite profile builder
  - deterministic LVN extraction helper
affects: [phase-07-plan-02, phase-07-plan-03, phase-09-full-strategy-integration]
tech-stack:
  added: []
  patterns: [shared histogram-to-level helpers, causal prior-window composites, explicit quality metadata]
key-files:
  created: [src/vwap_revert/indicators/volume_profile.py, tests/indicators/test_volume_profile.py]
  modified: [src/vwap_revert/indicators/__init__.py]
key-decisions:
  - "Reused Phase 3 session-level POC and value-area tie-break rules for every completed histogram family."
  - "Null HTF levels and histograms when the prior window mixes multiple front symbols instead of blending roll-discontinuous price regimes."
  - "LVN detection requires both raw local minima and smoothed confirmation before prominence filtering."
patterns-established:
  - "Phase 7 profile builders emit one row per trading_date with bucket lists, derived levels, trade-row counts, and quality_status."
  - "HTF composites are built from strictly prior daily profile rows, never same-day daily data."
requirements-completed: [STRC-02, STRC-03, STRC-04, STRC-05]
duration: inline
completed: 2026-04-02
---

# Phase 07 Plan 01: Volume Profile Core Summary

**Completed-session overnight, daily RTH, and prior-only HTF profile builders with deterministic LVN extraction and mixed-roll nulling**

## Performance

- **Duration:** inline
- **Started:** 2026-04-02
- **Completed:** 2026-04-02T22:31:59-04:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added a new `volume_profile` indicator module that builds overnight, daily RTH, and HTF profile summaries from trade rows only.
- Preserved Phase 3 structural semantics by reusing deterministic POC and contiguous 70% value-area rules.
- Locked causal behavior and LVN/mixed-roll edge cases with focused unit coverage.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing unit tests for overnight, daily, HTF, and LVN profile primitives** - `eedda91` (test)
2. **Task 2: Implement the Phase 7 profile core and export it from the indicators package** - `ed18376` (feat)

## Files Created/Modified
- `src/vwap_revert/indicators/volume_profile.py` - Core volume-profile builders, histogram helpers, HTF composition, and LVN detection.
- `src/vwap_revert/indicators/__init__.py` - Package export updated to expose `volume_profile`.
- `tests/indicators/test_volume_profile.py` - Unit coverage for overnight, daily, HTF causality, mixed-roll nulling, and LVN stability.

## Decisions Made
- Reused `_compute_session_levels` from Phase 3 so every profile family shares the same POC/value-area semantics.
- Treated mixed front-symbol HTF windows as unusable and emitted `mixed_roll_window` metadata with null HTF levels.
- Kept LVN outputs list-typed at the profile level so later enrichment work can choose how to project nearest nodes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected three test expectations to match inherited Phase 3 tie-break rules**
- **Found during:** Task 2
- **Issue:** Initial RED assertions assumed different value-area and composite POC outcomes than the repo's existing deterministic logic.
- **Fix:** Updated the overnight VAL, prior-day VAL, and HTF POC assertions to the actual inherited tie-break behavior.
- **Files modified:** `tests/indicators/test_volume_profile.py`
- **Verification:** `python -m pytest tests/indicators/test_volume_profile.py -q`
- **Committed in:** `ed18376`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The deviation aligned the new tests with the existing structural contract; no scope expansion.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None.

## Next Phase Readiness
- Ready for Phase 07 Plan 02 to project these profile families onto row-aligned structural outputs.
- Planning-state files were not updated here because the execution ownership for this task was limited to the summary and indicator/test files.

## Self-Check: PASSED
- Found summary file on disk.
- Verified task commits `eedda91` and `ed18376` exist in git history.

---
*Phase: 07-volume-profile-engine*
*Completed: 2026-04-02*
