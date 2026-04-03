---
phase: 07
slug: volume-profile-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 07 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 8.4.2` installed locally; repo declares `pytest>=9.0.2,<10` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_volume_profile.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_volume_profile.py -q`
- **After every plan wave:** Run `python -m pytest tests/indicators/test_volume_profile.py tests/indicators/test_volume_profile_validation.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | STRC-02 | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_overnight_profile_uses_completed_globex_rows_only -q` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | STRC-03 | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_daily_profiles_build_tick_aligned_histograms_and_prior_day_levels -q` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | STRC-04 | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_htf_composite_excludes_current_session_and_tracks_window_coverage -q` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | STRC-05 | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_lvn_detection_prefers_stable_local_minima -q` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 1 | STRC-06 | unit | `python -m pytest tests/indicators/test_volume_profile.py::test_enriched_output_carries_htf_balance_edges_and_quality_status -q` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | STRC-02, STRC-03, STRC-04, STRC-05, STRC-06 | integration | `python -m pytest tests/indicators/test_volume_profile_validation.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/indicators/test_volume_profile.py` - deterministic unit coverage for overnight profiles, daily histogram construction, HTF causality, LVN detection, partial-window quality states, and Phase 3 compatibility
- [ ] `tests/indicators/test_volume_profile_validation.py` - CLI and artifact coverage for all Phase 7 outputs and validation exports
- [ ] Roll-window fixture data - explicit sample sessions around a quarterly roll to force an HTF composite policy test instead of leaving it implicit
- [ ] Pytest cache warning mitigation - this workspace can run tests, but `pytest` warns that `.pytest_cache` cannot be created under the repo root

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Compare overnight, daily, and HTF profile levels against an external chart profile for selected validation sessions | STRC-02, STRC-03, STRC-05, STRC-06 | Repo tests can validate deterministic math and artifacts, but chart alignment still needs human inspection against a reference profile platform | Run the Phase 7 CLI with selected `--validation-date` values, open the generated validation CSV and manifest, and compare emitted overnight `POC/VAH/VAL`, daily profile levels, HTF balance edges, and LVN prices against the corresponding chart sessions |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
