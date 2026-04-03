---
phase: 05-trade-simulation-engine
verified: 2026-04-02T19:06:27-04:00
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "Confirm the configurable commission baseline matches the intended broker/prop cost model"
    expected: "The default round-trip commission of 5.0 is acceptable for the user's intended execution model, or is adjusted knowingly"
    why_human: "Code and tests prove the parameter exists and is applied once per trade, but they cannot confirm the user's real-world baseline assumption"
---

# Phase 5: Trade Simulation Engine Verification Report

**Phase Goal:** Mechanical trade replay producing realistic per-trade results with transaction cost modeling
**Verified:** 2026-04-02T19:06:27-04:00
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | System enters trades after setup conditions are met and exits at daily VWAP reversion target | ✓ VERIFIED | `open_trade_from_setup(...)` enters immediately on the setup row and preserves the setup timestamp; `replay_single_trade(...)` exits on executable-side VWAP checks with `target_vwap` in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L185) and [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L229). Locked by `test_enters_immediately_from_setup_event` and `test_vwap_target_uses_executable_quote_side` in [tests/indicators/test_trade_simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation.py#L119). |
| 2 | Every trade includes slippage and round-trip commissions | ✓ VERIFIED | Entry/exit fills use executable bid/ask plus configurable extra impact in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L146); net dollars subtract commission exactly once in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L175). Covered by `test_fill_prices_apply_bbo_side_and_additional_impact` and `test_round_trip_commission_reduces_net_pnl` in [tests/indicators/test_trade_simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation.py#L151). |
| 3 | Only one position is open at a time and overlapping setups are skipped | ✓ VERIFIED | `simulate_trades(...)` skips setups whose `ts_recv <= active_exit_ts` and records `position_active` in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L360). Covered by `test_overlapping_setups_are_skipped_while_position_active` in [tests/indicators/test_trade_simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation.py#L267). |
| 4 | Stop-loss triggers from executable-side MAE and session-end liquidation closes open trades at 16:00 ET | ✓ VERIFIED | Replay computes MAE from exit-side quotes, resolves same-row stop/target conflicts conservatively to `stop_loss`, and force-closes on the first row at or after `session_exit_time` in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L266). Covered by `test_stop_loss_uses_executable_mae_and_adverse_first_ordering` and `test_session_end_forces_exit_at_1600_et` in [tests/indicators/test_trade_simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation.py#L223). |
| 5 | A single CLI command rebuilds deterministic Phase 5 trade artifacts with Phase 6-ready fields | ✓ VERIFIED | `build-phase5-trade-simulation` builds `SimulationConfig`, calls `write_trade_simulation_artifacts(...)`, and emits trade log, skipped setup log, validation CSV, and manifest in [src/vwap_revert/cli.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/cli.py#L201) and [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L401). Covered by `test_cli_writes_phase5_trade_artifacts` in [tests/indicators/test_trade_simulation_validation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation_validation.py#L81). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `src/vwap_revert/simulation.py` | Phase 5 replay engine, pricing, batch output, artifact writer | ✓ VERIFIED | Exists, substantive, wired from CLI/tests, and data flows from Phase 4 parquet inputs through replay to persisted outputs. |
| `src/vwap_revert/cli.py` | Phase 5 build subcommand and config wiring | ✓ VERIFIED | Exists, substantive, and calls `write_trade_simulation_artifacts(...)` through `build_phase5_trade_simulation(...)`. |
| `tests/indicators/test_trade_simulation.py` | Deterministic unit coverage for entry, costs, exits, and overlap skipping | ✓ VERIFIED | Covers all core replay behaviors tied to TSIM-01/02/03/04/05/07/08. |
| `tests/indicators/test_trade_simulation_validation.py` | Integration coverage for CLI outputs and artifact schema | ✓ VERIFIED | Covers deterministic output filenames, CSV columns, and validation manifest keys. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `src/vwap_revert/indicators/setup_detection.py` | `src/vwap_revert/simulation.py` | Setup event columns consumed directly without re-derivation | ✓ WIRED | `open_trade_from_setup(...)` consumes `ts_recv`, `setup_direction`, `daily_vwap`, quote fields, and context fields expected from Phase 4 in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L185). |
| `src/vwap_revert/indicators/vwap.py` | `src/vwap_revert/simulation.py` | Daily VWAP target is consumed directly from enriched row state | ✓ WIRED | Replay compares executable exit-side quote to `target_price`/`daily_vwap` without re-deriving VWAP in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L278). |
| `src/vwap_revert/cli.py` | `src/vwap_revert/simulation.py` | Phase 5 command loads Phase 4 artifacts and emits trade-level outputs | ✓ WIRED | `build_phase5_trade_simulation(...)` constructs config and delegates to `write_trade_simulation_artifacts(...)` in [src/vwap_revert/cli.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/cli.py#L201). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `src/vwap_revert/simulation.py` | `entry_price` / `direction` / setup context | Phase 4 setup rows passed into `open_trade_from_setup(...)` | Yes | ✓ FLOWING |
| `src/vwap_revert/simulation.py` | `exit_reason`, `exit_price`, `mae_points`, `net_dollars` | Phase 4 enriched replay rows scanned by `replay_single_trade(...)` | Yes | ✓ FLOWING |
| `src/vwap_revert/simulation.py` | `trade_log`, `skipped_setups`, validation export, manifest | `simulate_trades(...)` result written by `write_trade_simulation_artifacts(...)` | Yes | ✓ FLOWING |
| `src/vwap_revert/cli.py` | Phase 5 output artifacts | CLI args -> `SimulationConfig` -> artifact writer | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Core Phase 5 replay behavior | `python -m pytest tests/indicators/test_trade_simulation.py -q` | `7 passed` | ✓ PASS |
| Phase 5 CLI artifact generation | `python -m pytest tests/indicators/test_trade_simulation_validation.py -q` | `1 passed` | ✓ PASS |
| Full Phase 5 regression surface | `python -m pytest tests/indicators/test_trade_simulation.py tests/indicators/test_trade_simulation_validation.py -q` | `8 passed` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| TSIM-01 | 05-01, 05-03 | System simulates trade entry after setup conditions are met | ✓ SATISFIED | Immediate entry is implemented by `open_trade_from_setup(...)` in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L185) and locked by [tests/indicators/test_trade_simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation.py#L119). |
| TSIM-02 | 05-02, 05-03 | System exits trades at VWAP reversion targets | ✓ SATISFIED | Executable-side VWAP target logic exists in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L278) and is covered by [tests/indicators/test_trade_simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/tests/indicators/test_trade_simulation.py#L184). |
| TSIM-03 | 05-01, 05-03 | System models slippage | ✓ SATISFIED | Fill helpers model spread crossing from BBO plus optional extra impact in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L146). |
| TSIM-04 | 05-01, 05-03 | System models round-trip commissions | ✓ SATISFIED | `pnl_dollars(...)` subtracts configurable round-trip commission once in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L175). |
| TSIM-05 | 05-03 | System enforces one-trade-at-a-time position management | ✓ SATISFIED | Overlap skipping and `position_active` diagnostics exist in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L369). |
| TSIM-07 | 05-02, 05-03 | System applies stop-loss logic based on MAE thresholds | ✓ SATISFIED | Replay computes adverse move from exit-side quotes and resolves stop-first on same-row ambiguity in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L272). |
| TSIM-08 | 05-02, 05-03 | System exits any open position at session end | ✓ SATISFIED | Session-end liquidation occurs on first row at or after `16:00 ET` in [src/vwap_revert/simulation.py](/c:/Users/pranav/Desktop/trading/vwap revert/src/vwap_revert/simulation.py#L318). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| None | - | No Phase 5 stub/placeholder patterns found in implementation or tests scanned | ℹ️ Info | No blocker or warning-level anti-patterns detected in the verified Phase 5 files. |

### Human Verification Required

### 1. Commission Baseline Review

**Test:** Run the Phase 5 build with the intended research configuration and review whether the default `round_trip_commission=5.0` matches the intended broker or prop-fee model.
**Expected:** The chosen commission baseline is accepted intentionally, or adjusted before downstream analytics rely on it.
**Why human:** Automated checks can confirm configurability and application, not whether `5.0` is the right real-world assumption.

### Gaps Summary

No implementation gaps were found for the Phase 05 goal or the requested requirement set. The remaining work is limited to confirming the commission default against the intended trading model; the same-row stop-first rule is now surfaced in artifact metadata and covered by tests.

---

_Verified: 2026-04-02T19:06:27-04:00_
_Verifier: Claude (gsd-verifier)_
