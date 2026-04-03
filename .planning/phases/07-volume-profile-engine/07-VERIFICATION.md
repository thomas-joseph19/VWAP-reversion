---
phase: 07-volume-profile-engine
verified: 2026-04-03T03:23:25.1585899Z
status: human_needed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 3/5
  gaps_closed:
    - "HTF 180-day rolling composite profile updates daily without look-ahead bias using completed sessions."
    - "Balance area extremes are identified from the HTF composite profile edges."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Compare exported overnight, daily, HTF, and LVN levels against an external chart profile for selected validation sessions."
    expected: "Validation CSV levels align with the reference profile platform for the same sessions, including mixed-roll HTF dates."
    why_human: "External chart parity is outside this workspace; automated checks only verify deterministic local math, wiring, and regression behavior."
---

# Phase 7: Volume Profile Engine Verification Report

**Phase Goal:** Full structural level detection from daily and HTF volume profiles replacing simple prior-day VA proxy.  
**Verified:** 2026-04-03T03:23:25.1585899Z  
**Status:** human_needed  
**Re-verification:** Yes - after `07-04` gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Daily volume profiles produce correct price x volume histograms at configurable tick resolution | ✓ VERIFIED | `build_daily_rth_profiles` emits tick-snapped bucket lists and derived levels in [src/vwap_revert/indicators/volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/volume_profile.py), with exact histogram assertions in [tests/indicators/test_volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_volume_profile.py). |
| 2 | HTF 180-day rolling composite profile updates daily without look-ahead bias using completed sessions | ✓ VERIFIED | `build_htf_profiles` slices strictly prior daily rows, bridges mixed-roll windows onto the target contract axis, and computes populated HTF levels at [src/vwap_revert/indicators/volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/volume_profile.py). Mixed-roll behavior is locked by `test_htf_composite_aligns_mixed_roll_windows_onto_current_contract_axis` in [tests/indicators/test_volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_volume_profile.py). |
| 3 | Low Volume Nodes are detected from valleys in the profile distribution | ✓ VERIFIED | `detect_lvn_prices` applies deterministic smoothing and prominence checks at [src/vwap_revert/indicators/volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/volume_profile.py), and the fixed-fixture LVN contract passes in [tests/indicators/test_volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_volume_profile.py). |
| 4 | Balance area extremes are identified from the HTF composite profile edges | ✓ VERIFIED | HTF `POC/VAH/VAL` are populated for mixed-roll mature windows in [src/vwap_revert/indicators/volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/volume_profile.py), propagated through row enrichment, and asserted non-null in both [tests/indicators/test_volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_volume_profile.py) and [tests/indicators/test_volume_profile_validation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_volume_profile_validation.py). |
| 5 | Overnight value area is computed from Globex data before each RTH open | ✓ VERIFIED | `build_overnight_profiles` filters `is_overnight` trade rows only and emits same-day overnight `POC/VAH/VAL` in [src/vwap_revert/indicators/volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/volume_profile.py), covered by `test_overnight_profile_uses_completed_globex_rows_only` in [tests/indicators/test_volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_volume_profile.py). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/vwap_revert/indicators/volume_profile.py` | Daily, overnight, HTF, enrichment, artifact, and validation logic | ✓ VERIFIED | Substantive implementation with roll-bridged HTF assembly, enrichment propagation, validation export writing, and no remaining mixed-roll null short-circuit. |
| `src/vwap_revert/cli.py` | Dedicated Phase 7 rebuild command | ✓ VERIFIED | `build-phase7-volume-profile` rebuilds all Phase 7 outputs from the canonical cache and writes validation artifacts. |
| `tests/indicators/test_volume_profile.py` | Core unit coverage | ✓ VERIFIED | Covers overnight, daily, HTF causality, mixed-roll bridging, LVN detection, and row-level enrichment availability. |
| `tests/indicators/test_volume_profile_validation.py` | End-to-end artifact and CLI coverage | ✓ VERIFIED | Verifies artifact names, validation CSV schema, manifest keys, and populated mixed-roll HTF outputs through the CLI. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `src/vwap_revert/data_pipeline/sessions.py` | `src/vwap_revert/indicators/volume_profile.py` | Reuse `trading_date`, `is_overnight`, and `is_rth` labels | ✓ WIRED | Phase 7 builders require and consume the canonical session columns instead of re-deriving boundaries. |
| `src/vwap_revert/indicators/structural_levels.py` | `src/vwap_revert/indicators/volume_profile.py` | Shared deterministic POC and value-area logic | ✓ WIRED | `volume_profile.py` imports `_compute_session_levels` and `attach_prior_day_structural_levels`. |
| `src/vwap_revert/indicators/volume_profile.py` | `src/vwap_revert/cli.py` | Artifact writing and validation export | ✓ WIRED | The CLI delegates to `write_volume_profile_artifacts` and `write_volume_profile_validation_export`. |
| Daily profile rows | HTF profile rows | Prior-only rolling composite with roll bridging | ✓ WIRED | `build_htf_profiles` uses strictly earlier daily profiles and applies cumulative roll-boundary deltas before HTF aggregation. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/vwap_revert/indicators/volume_profile.py` | `overnight_poc/overnight_vah/overnight_val` | Overnight trade rows filtered by `is_overnight` and `side in {"A","B"}` | Yes | ✓ FLOWING |
| `src/vwap_revert/indicators/volume_profile.py` | `daily_rth_poc/daily_rth_vah/daily_rth_val` | RTH trade rows filtered by `is_rth` and snapped to `0.25` buckets | Yes | ✓ FLOWING |
| `src/vwap_revert/indicators/volume_profile.py` | `htf_poc/htf_vah/htf_val` | Prior completed daily profiles shifted onto the target session contract axis before aggregation | Yes | ✓ FLOWING |
| `src/vwap_revert/indicators/volume_profile.py` | Row-level `htf_*`, `phase7_quality_status`, `roll_adjustment_applied`, `roll_anchor_symbol` | HTF summary join inside `attach_volume_profile_levels` | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Phase 7 unit and integration coverage | `python -m pytest tests/indicators/test_volume_profile.py tests/indicators/test_volume_profile_validation.py -q` | `9 passed, 1 warning` | ✓ PASS |
| Downstream compatibility across structural, setup, simulation, analytics, and Phase 7 suites | `python -m pytest tests/indicators/test_structural_levels.py tests/indicators/test_structural_levels_validation.py tests/indicators/test_setup_detection.py tests/indicators/test_setup_detection_validation.py tests/indicators/test_trade_simulation.py tests/indicators/test_trade_simulation_validation.py tests/indicators/test_core_analytics.py tests/indicators/test_core_analytics_validation.py tests/indicators/test_volume_profile.py tests/indicators/test_volume_profile_validation.py -q` | `30 passed, 1 warning` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| STRC-02 | 07-01, 07-02, 07-03 | System computes overnight value area edges (globex session before RTH) | ✓ SATISFIED | Overnight builder emits same-day `POC/VAH/VAL` from completed Globex rows and enrichment carries them row-level. |
| STRC-03 | 07-01, 07-03 | System builds daily volume profiles (price x volume histogram at configurable tick resolution) | ✓ SATISFIED | Daily profile artifacts persist tick-aligned histograms and derived levels. |
| STRC-04 | 07-01, 07-03, 07-04 | System builds HTF volume profile (rolling 180-day composite) without look-ahead bias | ✓ SATISFIED | HTF builder uses only prior daily sessions and now bridges mixed-roll windows onto the target-axis rather than nulling them. |
| STRC-05 | 07-01, 07-02, 07-03 | System identifies Low Volume Nodes (LVNs) from volume profiles | ✓ SATISFIED | LVN extraction is deterministic and exposed in profile artifacts plus scalar nearest-LVN enrichment fields. |
| STRC-06 | 07-02, 07-03, 07-04 | System identifies balance area extremes from HTF volume profiles | ✓ SATISFIED | HTF `POC/VAH/VAL` remain populated through mixed-roll mature windows and propagate into row-level Phase 7 outputs. |

### Anti-Patterns Found

No blocker anti-patterns found in the verified Phase 7 files. The only empty-list returns in [src/vwap_revert/indicators/volume_profile.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/indicators/volume_profile.py) are bounded helper behavior for insufficient LVN inputs and are covered by tests, not user-visible stubs.

### Human Verification Required

### 1. External Profile Alignment

**Test:** Run the Phase 7 CLI for selected validation dates and compare overnight, daily, LVN, and HTF outputs against a reference charting platform volume profile.  
**Expected:** Exported `overnight_poc/vah/val`, daily profile levels, HTF balance edges, and LVN references align with the chart for the same sessions, including a mixed-roll HTF date.  
**Why human:** External chart parity cannot be verified programmatically in this workspace.

### Gaps Summary

The prior HTF blocker is closed. The mixed-roll path no longer short-circuits to empty histograms and null HTF levels; instead, it bridges completed prior-session histograms onto the target contract axis and keeps HTF balance edges available through row-level enrichment and CLI validation outputs. Automated verification now shows full must-have coverage with no remaining code gaps. The only outstanding item is manual comparison against an external charting platform, so the phase is in `human_needed` rather than `gaps_found`.

---

_Verified: 2026-04-03T03:23:25.1585899Z_  
_Verifier: Claude (gsd-verifier)_
