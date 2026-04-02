---
phase: 04
slug: setup-detection
status: active
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-02
---

# Phase 04 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 8.4.2` installed locally; repo declares `pytest>=9.0.2,<10` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_setup_detection.py -q` |
| **Full suite command** | `python -m pytest tests/indicators -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_setup_detection.py -q`
- **After every plan wave:** Run `python -m pytest tests/indicators -q`
- **Before `$gsd-verify-work`:** Full indicators suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | VWAP-03 | unit | `python -m pytest tests/indicators/test_setup_detection.py -q` | ✅ | ✅ green |
| 04-01-02 | 01 | 1 | SGNL-01 | unit | `python -m pytest tests/indicators/test_setup_detection.py -q` | ✅ | ✅ green |
| 04-01-03 | 01 | 1 | SGNL-02 | unit | `python -m pytest tests/indicators/test_setup_detection.py -q` | ✅ | ✅ green |
| 04-02-01 | 02 | 2 | SGNL-03 | integration | `python -m pytest tests/indicators/test_setup_detection_validation.py -q` | ✅ | ✅ green |
| 04-02-02 | 02 | 2 | SGNL-01, SGNL-02, SGNL-03 | integration | `python -m pytest tests/indicators -q` | ✅ | ✅ green |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [x] `tests/indicators/test_setup_detection.py` - deterministic unit coverage for actionable-price sigma math, inclusive ET time-window gating, direction assignment, and transition-based setup emission
- [x] `tests/indicators/test_setup_detection_validation.py` - artifact writer and CLI coverage for enriched setup parquet, setup-log parquet, and validation export outputs
- [x] Shared fixture frame with at least two `trading_date` values, trade rows, quote-only rows, and bid/ask columns so per-day transition resets can be tested

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Setup-log spot check against sampled sessions | SGNL-03 | The workspace can verify deterministic outputs, but only a human can confirm the logged candidates match intended chart behavior on selected dates | Build the Phase 4 artifacts for at least two sampled sessions, open the validation export, and confirm the first qualifying setup row per excursion matches the expected VWAP-extension plus structural-confluence event in the 09:30-11:30 ET window |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing test references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** automated checks complete; manual setup-log spot check pending
