---
phase: 06
slug: core-analytics-output
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-02
---

# Phase 06 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 locally, repo dev pin `>=9.0.2,<10` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_core_analytics.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_core_analytics.py -q`
- **After every plan wave:** Run `python -m pytest tests/indicators/test_core_analytics.py tests/indicators/test_core_analytics_validation.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | ANLY-01 | unit | `python -m pytest tests/indicators/test_core_analytics.py::test_prepare_trade_log_adds_ticks_and_preserves_phase5_context -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | ANLY-02 | unit | `python -m pytest tests/indicators/test_core_analytics.py::test_compute_performance_metrics_handles_wins_losses_drawdown_and_sharpe_edges -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | ANLY-03 | integration | `python -m pytest tests/indicators/test_core_analytics_validation.py -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | ANLY-01, ANLY-02, ANLY-03 | integration | `python -m pytest tests/indicators/test_core_analytics.py tests/indicators/test_core_analytics_validation.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/indicators/test_core_analytics.py` - unit coverage for analytics-ready trade-log enrichment and deterministic metric formulas
- [ ] `tests/indicators/test_core_analytics_validation.py` - CLI and artifact validation coverage for Phase 6 outputs
- [ ] Phase 6 fixture trade-log data covering wins, losses, no-loss edge cases, and zero-variance Sharpe handling

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Review the selected Sharpe convention for research usefulness | ANLY-02 | Automated tests can prove consistency, but they cannot decide whether the chosen per-trade Sharpe interpretation is the best long-term baseline | Inspect `phase6_metrics.json` and confirm the Sharpe formula and null policy are documented intentionally |
| Spot-check exported CSV/JSON artifacts for analyst readability | ANLY-03 | Tests can validate schema and alignment, but they cannot confirm the artifacts are convenient for manual review | Run the Phase 6 CLI on sample data, open the CSV/JSON, and confirm filenames, columns, and metadata are understandable without code inspection |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-02
