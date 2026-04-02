---
phase: 03
slug: simple-structural-levels
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 03 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 8.4.2` installed locally; repo declares `pytest>=9.0.2,<10` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_structural_levels.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_structural_levels.py -q`
- **After every plan wave:** Run `python -m pytest tests/indicators -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | STRC-01 | unit | `python -m pytest tests/indicators/test_structural_levels.py -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | STRC-01 | unit | `python -m pytest tests/indicators/test_structural_levels.py -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | STRC-07 | unit | `python -m pytest tests/indicators/test_structural_levels.py -q` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | STRC-01, STRC-07 | integration | `python -m pytest tests/indicators/test_structural_levels_validation.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/indicators/test_structural_levels.py` - deterministic coverage for `POC` ties, 70% value-area expansion, missing prior session handling, and proximity features
- [ ] `tests/indicators/test_structural_levels_validation.py` - CLI/artifact coverage for session-level parquet, enriched parquet, and validation export outputs
- [ ] Pytest cache warning mitigation - ignore the warning, disable cacheprovider, or direct pytest cache to a writable path if it interferes with automation

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Prior-day `VAH`/`VAL`/`POC` values match a reference volume-profile chart on sampled sessions | STRC-01 | The workspace has no integrated chart-platform oracle, so cross-platform profile comparison remains visual/manual | Build Phase 03 artifacts for at least 5 sampled sessions, compare the prior-day RTH profile levels against a reference chart, and record any mismatch beyond the project’s tolerated threshold |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
