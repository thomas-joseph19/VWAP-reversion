---
phase: 07-volume-profile-engine
plan: 03
subsystem: volume-profile-engine
tags:
  - cli
  - validation
  - integration
requires:
  - 07-02
provides:
  - Phase 7 CLI rebuild command
  - Validation CSV and manifest export
  - End-to-end artifact integration coverage
affects:
  - src/vwap_revert/cli.py
  - src/vwap_revert/indicators/volume_profile.py
  - tests/indicators/test_volume_profile_validation.py
tech_stack:
  added: []
  patterns:
    - Polars artifact export
    - CLI phase rebuild command
    - Validation manifest generation
key_files:
  created:
    - .planning/phases/07-volume-profile-engine/07-03-SUMMARY.md
    - tests/indicators/test_volume_profile_validation.py
  modified:
    - src/vwap_revert/cli.py
    - src/vwap_revert/indicators/volume_profile.py
key_decisions:
  - Reused the existing phase validation-export pattern with a dedicated `validation/` CSV plus `validation_sessions.json`.
  - Kept Phase 7 rebuild input bounded to `scan_canonical_cache(cache_root).collect()`.
  - Verified mixed-roll HTF windows export null HTF levels while still surfacing `htf_roll_mixed_window`.
requirements_completed:
  - STRC-02
  - STRC-03
  - STRC-04
  - STRC-05
  - STRC-06
duration: 12m
completed: 2026-04-02T22:47:05.5406580-04:00
---

# Phase 07 Plan 03: CLI Wiring and Validation Export Summary

Phase 7 now rebuilds daily, overnight, HTF, enriched, and validation outputs from the canonical cache through one deterministic CLI command.

## Completed Work

- Added `tests/indicators/test_volume_profile_validation.py` with a partitioned canonical-cache fixture and the required integration test `test_cli_writes_phase7_volume_profile_artifacts`.
- Added `write_volume_profile_validation_export(...)` in `src/vwap_revert/indicators/volume_profile.py` to emit `validation/volume_profile_validation_export.csv` and `validation/validation_sessions.json`.
- Added `build_phase7_volume_profile(...)`, `_parse_phase7_validation_dates(...)`, and the `build-phase7-volume-profile` subcommand in `src/vwap_revert/cli.py`.
- Confirmed the validation CSV schema includes overnight, prior-day, HTF, nearest-level, quality, and mixed-roll columns required by the plan.
- Confirmed the validation manifest records `bucket_size`, `htf_lookback_sessions`, deterministic artifact filenames, validation dates, and row count.

## Verification

- RED check passed: `python -m pytest tests/indicators/test_volume_profile_validation.py -q` failed before implementation because the `build-phase7-volume-profile` CLI command did not exist yet.
- GREEN check passed: `python -m pytest tests/indicators/test_volume_profile.py tests/indicators/test_volume_profile_validation.py -q`
- Additional plan verification passed: a temporary Phase 7 build confirmed the validation CSV is the filtered selected-date subset of `phase7_volume_profile_enriched.parquet` after normalizing CSV round-trip types, and the manifest recorded `bucket_size: 0.25` plus `htf_lookback_sessions: 180`.

## Commits

- `e5e146c` `test(07-03): add phase 7 CLI integration coverage`
- `937e048` `feat(07-03): wire phase 7 volume profile rebuild`

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None.

## Notes

- Broader planning state files were not modified in this execution because the task ownership boundary excluded them.

## Self-Check: PASSED

- Summary file created at `.planning/phases/07-volume-profile-engine/07-03-SUMMARY.md`
- Task commits `e5e146c` and `937e048` exist in git history
