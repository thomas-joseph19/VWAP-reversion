---
phase: 2
slug: daily-vwap-engine
status: draft
nyquist_compliant: false
wave_0_complete: true
created: 2026-04-02
---

# Phase 2 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_vwap.py -x` |
| **Full suite command** | `python -m pytest tests/indicators -x` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_vwap.py -x`
- **After every plan wave:** Run `python -m pytest tests/indicators -x`
- **Before `$gsd-verify-work`:** Full indicators suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | VWAP-01 | unit | `python -m pytest tests/indicators/test_vwap.py::test_daily_vwap_uses_rth_trade_rows_only -x` | no | pending |
| 2-01-02 | 01 | 1 | VWAP-02 | unit | `python -m pytest tests/indicators/test_vwap.py::test_sigma_bands_use_volume_weighted_expanding_formula -x` | no | pending |
| 2-01-03 | 01 | 1 | VWAP-01 | integration | `python -m pytest tests/indicators/test_vwap.py::test_indicator_columns_join_back_to_session_rows -x` | no | pending |
| 2-02-01 | 02 | 2 | VWAP-06 | integration | `python -m pytest tests/indicators/test_vwap_validation.py::test_validation_export_contains_comparison_columns -x` | no | pending |
| 2-02-02 | 02 | 2 | VWAP-06 | integration | `python -m pytest tests/indicators/test_vwap_validation.py::test_cli_writes_indicator_and_validation_artifacts -x` | no | pending |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reference-platform comparison across at least five sessions | VWAP-06 | TradingView or NinjaTrader values are external to the repo and require human comparison | Export the validation artifact, load the same dates on the reference platform, and confirm VWAP mismatches stay within 0.25 NQ points at sampled timestamps |
| DST-adjacent session sanity | VWAP-01 | The math is automated, but human review should confirm the chosen dates span normal and DST-adjacent sessions | Include at least one DST-adjacent session in the validation manifest and verify the 9:30 ET anchor visually |

---

## Validation Sign-Off

- [ ] All tasks have automated verification commands
- [ ] Sampling continuity preserved across both plans
- [ ] Manual chart-validation artifact exists for at least five sessions
- [ ] `nyquist_compliant: true` set in frontmatter after execution proves the checks

**Approval:** pending

