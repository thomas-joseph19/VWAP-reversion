---
phase: 05
slug: trade-simulation-engine
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-02
---

# Phase 05 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.4.2 locally, repo dev pin `>=9.0.2,<10` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `python -m pytest tests/indicators/test_trade_simulation.py -x` |
| **Full suite command** | `python -m pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/indicators/test_trade_simulation.py -x`
- **After every plan wave:** Run `python -m pytest tests/indicators/test_trade_simulation.py tests/indicators/test_trade_simulation_validation.py -x`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | TSIM-01 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_enters_immediately_from_setup_event -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | TSIM-03 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_fill_prices_apply_bbo_side_and_additional_impact -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | TSIM-04 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_round_trip_commission_reduces_net_pnl -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | TSIM-02 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_vwap_target_uses_executable_quote_side -x` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | TSIM-07 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_stop_loss_uses_executable_mae_and_adverse_first_ordering -x` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 2 | TSIM-08 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_session_end_forces_exit_at_1600_et -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 3 | TSIM-05 | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_overlapping_setups_are_skipped_while_position_active -x` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 3 | TSIM-01, TSIM-02, TSIM-03, TSIM-04, TSIM-05, TSIM-07, TSIM-08 | integration | `python -m pytest tests/indicators/test_trade_simulation.py tests/indicators/test_trade_simulation_validation.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/indicators/test_trade_simulation.py` - stubs and core replay behavior coverage for `TSIM-01`, `TSIM-02`, `TSIM-03`, `TSIM-04`, `TSIM-05`, `TSIM-07`, and `TSIM-08`
- [ ] `tests/indicators/test_trade_simulation_validation.py` - CLI and artifact validation coverage for Phase 5 outputs
- [ ] `src/vwap_revert/cli.py` command coverage for `build-phase5-trade-simulation`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Commission baseline sanity check against intended NQ assumptions | TSIM-04 | Default commission is a planning baseline and may need human confirmation against the user’s intended broker/prop model | Run the phase command, inspect config/docs for the default round-trip commission, and confirm it is documented as a configurable baseline assumption |
| Review same-second stop/target collision policy in output metadata | TSIM-07 | Automated tests can verify the implemented rule, but human review should confirm the policy is clearly documented as adverse-first for 1-second ambiguity | Generate a sample trade artifact and verify the collision policy is stated in artifact metadata or docs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-02
