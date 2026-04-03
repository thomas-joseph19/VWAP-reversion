---
phase: 07-volume-profile-engine
plan: 04
subsystem: indicators
tags: [polars, volume-profile, htf, contract-roll, validation]
requires:
  - phase: 07-03
    provides: Phase 7 CLI rebuild and validation export coverage
provides:
  - roll-bridged HTF composites across quarterly front-month changes
  - populated mixed-roll HTF balance edges in row-level Phase 7 enrichment
  - validation coverage that rejects null mixed-roll HTF outputs
affects: [phase-07-verification, phase-09-full-strategy-integration]
tech-stack:
  added: []
  patterns: [target-axis HTF roll bridging, cumulative roll-boundary delta alignment, HTF audit-field propagation]
key-files:
  created: [.planning/phases/07-volume-profile-engine/07-04-SUMMARY.md]
  modified: [src/vwap_revert/indicators/volume_profile.py, tests/indicators/test_volume_profile.py, tests/indicators/test_volume_profile_validation.py]
key-decisions:
  - "Mixed-roll HTF windows now stay causal by shifting prior completed-session histograms onto the target session contract axis with cumulative roll-boundary POC deltas."
  - "HTF quality status is determined by history completeness once a bridged composite exists; mixed-roll membership remains audit metadata instead of a nulling condition."
patterns-established:
  - "HTF roll alignment happens before histogram aggregation so POC, VAH, VAL, and LVN extraction operate on the current contract axis."
  - "Row-level Phase 7 enrichment carries HTF roll audit columns alongside populated HTF balance edges without changing the validation export schema."
requirements-completed: [STRC-04, STRC-06]
duration: 18 min
completed: 2026-04-02
---

# Phase 07 Plan 04: Mixed-Roll HTF Gap Closure Summary

**Quarterly-roll HTF composites now bridge prior-session histograms onto the current contract axis so mixed-roll windows keep usable POC, VAH, and VAL outputs through Phase 7 enrichment and validation**

## Performance

- **Duration:** 18 min
- **Started:** 2026-04-02T23:02:00-04:00
- **Completed:** 2026-04-02T23:19:56.5338807-04:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Rewrote the mixed-roll RED tests to require a deterministic bridged HTF composite, exposed roll-audit columns, and populated row-level HTF balance edges.
- Implemented cumulative roll-boundary alignment in `build_htf_profiles(...)` so strictly prior daily profiles still produce a usable current-axis HTF composite across quarterly rolls.
- Preserved downstream contracts by keeping validation artifact names and schema stable while making mixed-roll `htf_poc`, `htf_vah`, and `htf_val` non-null on mature windows.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite the mixed-roll HTF tests to require a usable bridged composite and available balance edges** - `920a024` (test)
2. **Task 2: Implement roll-bridged HTF composites and keep mixed-roll HTF edges populated through enrichment** - `8bf91ee` (feat)

## Files Created/Modified
- `.planning/phases/07-volume-profile-engine/07-04-SUMMARY.md` - Plan execution summary for the mixed-roll HTF gap closure.
- `src/vwap_revert/indicators/volume_profile.py` - Added roll-boundary delta bridging, HTF roll audit columns, and mixed-roll enrichment propagation.
- `tests/indicators/test_volume_profile.py` - Replaced mixed-roll nulling expectations with bridged HTF outputs and row-level availability checks.
- `tests/indicators/test_volume_profile_validation.py` - Updated CLI validation assertions to require non-null mixed-roll HTF balance edges.

## Decisions Made
- Used completed-session `daily_rth_poc` changes at front-symbol boundaries as the deterministic roll delta for shifting prior histograms onto the target contract axis.
- Kept `roll_mixed_window` and `source_front_symbols` as audit metadata while making completeness, not symbol diversity, drive HTF quality status once a bridged window exists.
- Joined `roll_adjustment_applied` and `roll_anchor_symbol` onto the enriched Phase 7 rows so downstream consumers can audit how mixed-roll HTF levels were produced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stabilized empty profile builders when a source family has no rows**
- **Found during:** Task 2 (Implement roll-bridged HTF composites and keep mixed-roll HTF edges populated through enrichment)
- **Issue:** The new row-level mixed-roll fixture exposed that `build_overnight_profiles(...)` and related empty-profile paths could return a schema-less frame and fail joins when no overnight rows existed.
- **Fix:** Added an explicit empty-frame helper so profile builders keep their expected columns even when a profile family is absent.
- **Files modified:** `src/vwap_revert/indicators/volume_profile.py`
- **Verification:** `python -m pytest tests/indicators/test_volume_profile.py tests/indicators/test_volume_profile_validation.py -q`
- **Committed in:** `8bf91ee`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The auto-fix kept the new mixed-roll coverage executable without broadening scope beyond Phase 7 profile correctness.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7 verification can now re-check the previously blocked HTF truths against populated mixed-roll windows.
- Planning-state files were not updated in this execution because task ownership for this turn was limited to the summary, indicator module, and owned tests.

## Self-Check: PASSED
- Found summary file on disk.
- Verified task commits `920a024` and `8bf91ee` exist in git history.

---
*Phase: 07-volume-profile-engine*
*Completed: 2026-04-02*
