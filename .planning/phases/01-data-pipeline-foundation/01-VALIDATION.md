---
phase: 1
slug: data-pipeline-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-02
---

# Phase 1 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` or `pyproject.toml` - add in Wave 0 |
| **Quick run command** | `python -m pytest tests/data_pipeline/test_sessions.py -x` |
| **Full suite command** | `python -m pytest tests/data_pipeline -x` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/data_pipeline/test_sessions.py -x`
- **After every plan wave:** Run `python -m pytest tests/data_pipeline -x`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | DATA-01 | integration | `python -m pytest tests/data_pipeline/test_ingest.py::test_reads_sample_day -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | DATA-02 | unit | `python -m pytest tests/data_pipeline/test_contracts.py::test_front_month_selected_by_daily_volume -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | DATA-03 | integration | `python -m pytest tests/data_pipeline/test_contracts.py::test_roll_map_records_symbol_changes -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 0 | DATA-04 | unit | `python -m pytest tests/data_pipeline/test_sessions.py::test_dst_transition_dates -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 0 | DATA-05 | unit | `python -m pytest tests/data_pipeline/test_sessions.py::test_globex_boundary_labels -x` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 0 | DATA-06 | integration | `python -m pytest tests/data_pipeline/test_cache.py::test_partitioned_cache_layout -x` | ❌ W0 | ⬜ pending |
| 1-01-07 | 01 | 0 | DATA-07 | unit | `python -m pytest tests/data_pipeline/test_quality.py::test_structural_vs_recoverable_errors -x` | ❌ W0 | ⬜ pending |
| 1-01-08 | 01 | 0 | DATA-08 | unit | `python -m pytest tests/data_pipeline/test_quality.py::test_gap_detection_and_holiday_reporting -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `python -m pip install pytest` - install the test framework missing from the local environment
- [ ] `tests/data_pipeline/test_ingest.py` - stubs for DATA-01
- [ ] `tests/data_pipeline/test_contracts.py` - stubs for DATA-02 and DATA-03
- [ ] `tests/data_pipeline/test_sessions.py` - stubs for DATA-04 and DATA-05
- [ ] `tests/data_pipeline/test_cache.py` - stubs for DATA-06
- [ ] `tests/data_pipeline/test_quality.py` - stubs for DATA-07 and DATA-08
- [ ] `pytest.ini` or `pyproject.toml` - shared pytest discovery config

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full-history cache rebuild finishes within the Phase 1 performance target | DATA-06 | Runtime depends on local disk throughput and the full 884-file dataset | Run the full pipeline against the local dataset, record wall-clock time for the first CSV-to-Parquet build and a second cache-backed load, and confirm the second load is under 30 seconds |
| Contract roll map matches known quarterly transitions | DATA-02 | DATA-03 | Requires spot-checking generated roll dates against expected quarterly NQ roll periods | Inspect the generated roll-map artifact around each quarterly roll and confirm the dominant symbol changes only when same-day outright volume leadership changes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
