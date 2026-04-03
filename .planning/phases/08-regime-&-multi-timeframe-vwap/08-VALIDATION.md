---
phase: 08
slug: regime-&-multi-timeframe-vwap
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-03
---

# Phase 08 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 8.4.2` installed locally; repo declares `pytest>=9.0.2,<10` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_regime.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_regime.py -q`
- **After every plan wave:** Run `python -m pytest tests/indicators/test_regime.py tests/indicators/test_regime_validation.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | REGM-01, REGM-02 | unit | `python -m pytest tests/indicators/test_regime.py::test_build_session_regimes_marks_insufficient_history_before_threshold_window -q` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | REGM-01, REGM-02 | unit | `python -m pytest tests/indicators/test_regime.py::test_build_session_regimes_labels_short_and_long_gamma_from_prior_completed_sessions -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | VWAP-04, VWAP-05 | unit | `python -m pytest tests/indicators/test_regime.py::test_attach_regime_and_multi_timeframe_vwap_resets_weekly_and_monthly_anchors -q` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | VWAP-04, VWAP-05, REGM-03 | unit | `python -m pytest tests/indicators/test_regime.py::test_attach_regime_and_multi_timeframe_vwap_bridges_roll_windows_onto_active_contract_axis -q` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | REGM-01, REGM-02, REGM-03, VWAP-04, VWAP-05 | integration | `python -m pytest tests/indicators/test_regime_validation.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/indicators/test_regime.py` - deterministic unit coverage for session-regime summaries, causal label shifting, weekly/monthly anchor resets, null-before-anchor behavior, and roll-bridge continuity
- [ ] `tests/indicators/test_regime_validation.py` - CLI and artifact coverage for the Phase 8 session-summary parquet, row-level enriched parquet, validation CSV, and manifest metadata
- [ ] Mixed-roll weekly/monthly fixture data - covered by `08-02-02` so higher-timeframe anchors are proven continuous across quarterly symbol changes
- [ ] Session-history fixture data - covered by `08-01-01` and `08-01-02` so insufficient-history and binary regime labels are both exercised deterministically

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Compare selected weekly/monthly VWAP values against a reference charting platform | VWAP-04, VWAP-05 | Repo tests validate deterministic math and artifact wiring, but external chart parity still requires human inspection | Run the Phase 8 CLI with selected `--validation-date` values, open `validation/regime_vwap_validation_export.csv`, and compare `weekly_vwap` and `monthly_vwap` against the corresponding reference chart sessions including at least one mixed-roll week and one month boundary |
| Spot-check whether short-gamma sessions show materially larger displacements than long-gamma sessions on sampled dates | REGM-02, REGM-03 | The proxy regime model is deterministic locally, but alignment with the author's qualitative regime expectations still needs human review | Inspect `phase8_session_regimes.parquet` and the validation CSV for selected dates, then compare observed setup/displacement context against the author's expected short-vs-long-gamma behavior |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 coverage is satisfied by Plan 01 regime-core tests, Plan 02 higher-timeframe VWAP unit coverage, and Plan 03 CLI integration coverage
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter after the Wave 1-3 coverage is implemented

**Approval:** pending
