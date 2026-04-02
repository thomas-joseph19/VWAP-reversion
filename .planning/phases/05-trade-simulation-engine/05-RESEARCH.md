# Phase 5: Trade Simulation Engine - Research

**Researched:** 2026-04-02
**Domain:** Mechanical trade replay for NQ VWAP-reversion setups
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Entry semantics
- **D-01:** Enter immediately when a Phase 4 setup event is emitted; Phase 5 does not wait for any extra continuation-failure confirmation.
- **D-02:** Use the Phase 4 setup direction as the trade direction directly: positive sigma extension produces a short reversion trade, and negative sigma extension produces a long reversion trade.
- **D-03:** Treat the setup log as the canonical trade-trigger surface for this MVP phase rather than re-deriving setup conditions inside the simulator.

### Fill and friction model
- **D-04:** Model fills from the contemporaneous BBO side without adding extra slippage: long entries and short exits use the ask, while short entries and long exits use the bid when quotes are available.
- **D-05:** Additional slippage defaults to zero because the intended environment is a simulated prop-firm-style evaluation rather than live market execution.
- **D-06:** Round-trip commissions remain in scope and should be configurable, with a realistic NQ default rate chosen during planning.

### Exit and stop policy
- **D-07:** The primary profit target is full reversion to the current daily VWAP, matching the roadmap's baseline Phase 5 success criterion.
- **D-08:** Use a configurable fixed stop-loss threshold in absolute NQ points for the MVP baseline, evaluated from maximum adverse excursion after entry.
- **D-09:** The default stop should be treated as a planning-time baseline rather than an optimized parameter, because the most profitable threshold cannot be known honestly before backtest results exist.

### Position management
- **D-10:** Only one live position may be open at a time across the entire strategy.
- **D-11:** If a new setup appears while a trade is active, skip it entirely instead of queuing, netting, or pyramiding.
- **D-12:** Force-close any still-open trade at the session-end cutoff defined by the roadmap, even if neither the VWAP target nor the stop-loss has been hit.

### Claude's Discretion
- Exact commission default, as long as it is realistic for NQ and configurable.
- The initial fixed stop distance, as long as it is documented as a non-optimized baseline for later analysis.
- Exact artifact schema for trade-level diagnostics beyond the required entry/exit/P&L fields.

### Deferred Ideas (OUT OF SCOPE)
- Continuation-failure refinement belongs to Phase 9, not this MVP simulation phase.
- Multi-target exits such as weekly VWAP or developing POC belong to later phases.
- Slippage sensitivity sweeps and richer live-execution realism can be added later if needed, but they are not the baseline requested here.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TSIM-01 | System simulates trade entry after setup conditions are met (post-failure confirmation) | Planning should honor `D-01`/`D-03`: use the Phase 4 emitted setup event as the entry trigger surface, not a new failure-confirmation layer. |
| TSIM-02 | System exits trades at VWAP reversion targets (daily VWAP as primary) | Use side-aware executable target checks against `daily_vwap` on the enriched row stream. |
| TSIM-03 | System models slippage (spread-crossing cost from BBO + configurable additional impact) | Use bid/ask-side fills as the built-in spread-crossing cost, plus configurable extra impact in points with default `0.0`. |
| TSIM-04 | System models round-trip commissions (configurable, default NQ standard rates) | Add a per-contract round-trip commission parameter, defaulting to a realistic all-in baseline and applied once per completed trade. |
| TSIM-05 | System enforces one-trade-at-a-time position management (no overlapping positions) | Replay setups chronologically with explicit `flat`/`open` state and mark overlapping setups as skipped. |
| TSIM-07 | System applies stop-loss logic based on maximum adverse excursion thresholds | Track post-entry adverse movement using executable exit-side quotes and stop out when MAE exceeds a fixed-point threshold. |
| TSIM-08 | System exits any open position at session end (time-based forced exit) | Force liquidation on the first row at or after `16:00:00 ET`, using the executable exit side and exit reason `session_end`. |
</phase_requirements>

## Summary

Phase 5 should stay narrow and deterministic. The simulator should not recalculate setups, should not introduce new confirmation logic, and should not adopt a generic backtesting framework. It should consume the existing Phase 4 setup log as the canonical trigger surface and the Phase 4 enriched row-level artifact as the canonical post-entry price path. This keeps the entry surface identical to the validated Phase 4 output and preserves the repo's current pattern of deterministic parquet artifacts plus explicit downstream consumption.

The critical implementation detail is to model everything from executable quote sides, not trade price or mid-price. For this phase, the BBO spread-crossing cost is already captured by filling longs on the ask and shorts on the bid at entry, then reversing that side logic on exit. Additional slippage should remain configurable but default to `0.0` per the locked decisions. Profit target checks, stop checks, MAE tracking, and session-end liquidation should all use the same executable-side logic so the trade log reflects what could actually be closed at the observed quote surface.

There are two planning-level ambiguities that must be resolved explicitly in the plan. First, the requirement text for `TSIM-01` still says "post-failure confirmation", but the locked Phase 5 context supersedes that and requires immediate entry on the Phase 4 event. Second, same-second stop/target conflicts cannot be ordered from 1-second BBO snapshots alone; the plan should adopt a conservative adverse-first tie-break when both conditions are true on the same row.

**Primary recommendation:** Build a small sequential replay engine over the Phase 4 setup log plus enriched row stream, with side-aware BBO fills, configurable fixed-point stop and commission defaults, single-position gating, and deterministic parquet/CSV artifacts for Phase 6.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.x | Runtime and CLI entrypoint | Already required by the repo and available locally (`Python 3.14.3`). |
| Polars | 1.39.x | Artifact loading, chronological filtering, joins, parquet output | Matches the existing repo pattern in Phases 2-4 and is the current project pin. |
| NumPy | 2.4.x | Direction/P&L math and any tight numeric helpers | Minimal numeric dependency already used by the project stack. |
| PyArrow | 23.0.1 | Parquet backend | Already pinned and installed; keeps artifact IO fast and consistent. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.4.2 local, repo dev pin `>=9.0.2,<10` | Unit and CLI validation | Use `python -m pytest`; the bare `pytest` command is not on `PATH` in this workspace. |
| tzdata | 2025.x | Timezone database on Windows | Needed indirectly for ET session-end handling on this machine. |
| dataclasses / pathlib | stdlib | Config and artifact paths | Use for the replay config and deterministic output metadata. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom sequential replay over Phase 4 artifacts | Backtrader / vectorbt / other framework | Adds framework abstractions the repo does not use and makes the Phase 4 artifact boundary less explicit. |
| Polars filtering and parquet artifacts | Pandas-only implementation | Inconsistent with the current codebase and less aligned with the project's existing transforms. |
| Simple BBO-side execution model | Intrabar/order-book simulation | Not supportable from 1-second top-of-book data and likely to create false precision. |

**Installation:**
```bash
python -m pip install -e .[dev]
```

**Version verification:**
- `polars 1.39.3` was visible on PyPI release history dated 2026-03-20; the local environment currently has `1.39.2`.
- `pyarrow 23.0.1` was visible on PyPI release history dated 2026-02-16; the local environment matches it.
- `pytest 9.0.2` was visible on PyPI release history dated 2025-12-06; the local environment currently has `8.4.2`.
- `numpy` is a local anomaly: the workspace and installed environment both reference `2.4.4`, but public PyPI search results surfaced `2.4.3` as the visible latest release. Treat the repo pin as authoritative for this phase unless dependency work is explicitly added.

## Architecture Patterns

### Recommended Project Structure
```text
src/
|-- vwap_revert/
|   |-- simulation.py      # Phase 5 replay engine, config, artifact writers
|   `-- cli.py             # add build-phase5-trade-simulation
tests/
`-- indicators/
    |-- test_trade_simulation.py
    `-- test_trade_simulation_validation.py
```

### Pattern 1: Consume Phase 4 Artifacts, Do Not Re-Derive Setups
**What:** Take the compact Phase 4 setup log as the only entry-trigger input and the Phase 4 enriched row stream as the only post-entry price path.
**When to use:** Always for this phase.
**Why:** It preserves `D-03`, keeps Phase 4 as the canonical signal boundary, and avoids subtle drift if setup predicates change.
**Example:**
```python
# Source: project pattern from src/vwap_revert/indicators/setup_detection.py
setup_log = pl.read_parquet(phase4_root / "phase4_setup_log.parquet").sort(["trading_date", "ts_recv"])
path_rows = pl.read_parquet(phase4_root / "phase4_setup_enriched.parquet").sort(["trading_date", "ts_recv"])
```

### Pattern 2: Small Sequential Replay Over Setups, Not Over the Full Dataset
**What:** Walk setup events in chronological order, open at most one position, then scan forward only through rows after that entry until exit.
**When to use:** For the core trade-simulation loop.
**Why:** Position state is inherently sequential, but the state space is tiny because the setup log is already pre-filtered.
**Example:**
```python
# Source: recommended extension of the existing phase-artifact pattern
for setup in setup_log.iter_rows(named=True):
    if active_trade is not None:
        skipped.append({"ts_recv": setup["ts_recv"], "reason": "position_active"})
        continue

    trade = open_trade_from_setup(setup, config)
    session_rows = path_rows.filter(
        (pl.col("trading_date") == setup["trading_date"]) &
        (pl.col("ts_recv") >= setup["ts_recv"])
    )
    active_trade = replay_trade(session_rows, trade, config)
    completed.append(active_trade.to_record())
    active_trade = None
```

### Pattern 3: Executable-Side Quote Logic Everywhere
**What:** Use ask-side prices for long entries and short exits; use bid-side prices for short entries and long exits; apply the same side-awareness to target and stop checks.
**When to use:** Entry fill, exit fill, target hit detection, stop hit detection, MAE tracking, and session-end liquidation.
**Why:** This is the only way to make `TSIM-03` true without double-counting spread or accidentally using non-executable prices.
**Example:**
```python
# Source: CME NQ tick spec + project decision D-04
def entry_fill(row: dict[str, float], direction: str, extra_impact_points: float) -> float:
    if direction == "long":
        return row["ask_px_00"] + extra_impact_points
    return row["bid_px_00"] - extra_impact_points

def exit_fill(row: dict[str, float], direction: str, extra_impact_points: float) -> float:
    if direction == "long":
        return row["bid_px_00"] - extra_impact_points
    return row["ask_px_00"] + extra_impact_points
```

### Pattern 4: Conservative Same-Row Exit Precedence
**What:** If target and stop are both true on the same 1-second row, exit via the adverse outcome.
**When to use:** Any time a single row satisfies both stop and target conditions.
**Why:** The data has no within-second path ordering. Adverse-first is conservative and avoids overstating edge.
**Example:**
```python
# Source: research recommendation for 1-second BBO ambiguity
if stop_hit and target_hit:
    exit_reason = "stop_loss"
elif stop_hit:
    exit_reason = "stop_loss"
elif target_hit:
    exit_reason = "target_vwap"
```

### Anti-Patterns to Avoid
- **Recomputing Phase 4 logic inside Phase 5:** It breaks the canonical trigger boundary and creates hidden drift.
- **Using last trade or midpoint for fills:** It understates spread-crossing cost and can create impossible executions.
- **Double-counting spread as extra slippage:** Bid/ask-side fills already include spread-crossing cost; extra impact is separate.
- **Scanning the full row stream for position state:** The replay only needs rows from the active trade's session after entry.
- **Using CME's broader trading day for exits:** This project explicitly force-closes at `16:00 ET`, not the exchange's wider session.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Generic backtesting engine | Portfolio/order framework with broker abstractions | A small deterministic replay loop over Phase 4 artifacts | The project is single-strategy, single-position, artifact-driven. |
| Intrasecond path reconstruction | Synthetic tick ordering inside a 1-second row | Conservative adverse-first tie-break | The dataset cannot prove within-second order. |
| Spread model on top of BBO-side fills | Separate spread debit formula | Entry/exit quote-side execution plus optional extra impact | Quote-side fills already encode spread crossing. |
| Signal regeneration | New setup detector inside the simulator | The existing Phase 4 setup log | Preserves locked decision `D-03` and avoids duplicate logic. |
| Optimized stop discovery | Parameter search in this phase | A documented baseline fixed stop distance | The context explicitly forbids claiming an optimum before backtest results exist. |

**Key insight:** The main risk in this phase is not sophistication; it is inconsistency. Every custom layer added beyond the Phase 4 artifact boundary increases the chance of hidden drift, cost mis-modeling, or accidental optimism.

## Common Pitfalls

### Pitfall 1: Target Checks Use the Wrong Side of the Market
**What goes wrong:** A long trade is marked as having hit VWAP because the last trade or midpoint reached VWAP, even though the executable bid never did.
**Why it happens:** Developers think in chart prices instead of executable prices.
**How to avoid:** For long exits, require `bid_px_00 >= daily_vwap`; for short exits, require `ask_px_00 <= daily_vwap`.
**Warning signs:** Trades exit at prices better than the contemporaneous bid/ask.

### Pitfall 2: Spread Is Charged Twice
**What goes wrong:** The simulator fills on bid/ask and then subtracts an additional spread-crossing cost again.
**Why it happens:** Requirement `TSIM-03` is read as "add spread + slippage" rather than "bid/ask fill already is the spread component."
**How to avoid:** Treat quote-side fills as the spread cost and reserve `additional_slippage_points` for only the configurable extra impact.
**Warning signs:** Net results worsen by roughly one spread more than expected on every round trip.

### Pitfall 3: One-Position Logic Is Enforced After the Fact
**What goes wrong:** The engine simulates all setups independently and removes overlaps later.
**Why it happens:** Vectorized thinking is applied to a sequential state problem.
**How to avoid:** Replay setups in chronological order and decide skip/open in the same loop.
**Warning signs:** Trade logs show overlapping timestamps or skipped-trade counts are impossible to reconcile.

### Pitfall 4: Stop Logic Uses Price Extremes That Were Not Executable
**What goes wrong:** A short trade stops because the last trade price exceeded the stop, but the ask did not.
**Why it happens:** MAE is measured from mid/trade prices instead of the executable cover/exit side.
**How to avoid:** For longs, compute adverse excursion from bid; for shorts, from ask.
**Warning signs:** Stops trigger earlier than the visible quote path would allow.

### Pitfall 5: Session-End Exit Uses 16:15 ET or CME ETH Boundaries
**What goes wrong:** Trades remain open beyond the roadmap cutoff.
**Why it happens:** CME product hours are consulted instead of the project convention.
**How to avoid:** Hardcode the project cutoff as `16:00:00 ET` for Phase 5 and document the intentional divergence from wider exchange trading hours.
**Warning signs:** Trades persist into the post-16:00 ET portion of the row stream.

### Pitfall 6: Same-Row Stop/Target Conflicts Are Resolved Optimistically
**What goes wrong:** The simulator credits the target whenever both stop and target are true on the same row.
**Why it happens:** The engine wants a deterministic answer but picks the favorable one.
**How to avoid:** Use adverse-first precedence and record that policy in artifact metadata.
**Warning signs:** A suspicious number of tiny winners occur on volatile rows with wide quote movement.

## Code Examples

Verified project-aligned patterns:

### Trade Replay Skeleton
```python
# Source: project artifact pattern + Phase 5 research recommendation
from dataclasses import dataclass
from datetime import time

import polars as pl


@dataclass(frozen=True)
class SimulationConfig:
    stop_loss_points: float = 20.0
    round_trip_commission: float = 5.00
    additional_slippage_points: float = 0.0
    session_exit_time: time = time(16, 0)


def simulate_trades(setup_log: pl.DataFrame, path_rows: pl.DataFrame, config: SimulationConfig) -> pl.DataFrame:
    completed: list[dict[str, object]] = []
    active_exit_ts = None

    for setup in setup_log.sort(["trading_date", "ts_recv"]).iter_rows(named=True):
        if active_exit_ts is not None and setup["ts_recv"] <= active_exit_ts:
            completed.append({"setup_ts": setup["ts_recv"], "status": "skipped_position_active"})
            continue

        trade_rows = path_rows.filter(
            (pl.col("trading_date") == setup["trading_date"]) &
            (pl.col("ts_recv") >= setup["ts_recv"])
        )
        trade = replay_single_trade(setup, trade_rows, config)
        active_exit_ts = trade["exit_ts"]
        completed.append(trade)

    return pl.DataFrame(completed)
```

### Net P&L Convention
```python
# Source: CME NQ contract multiplier + Phase 5 cost model
POINT_VALUE = 20.0


def pnl_dollars(direction: str, entry_price: float, exit_price: float, round_trip_commission: float) -> float:
    sign = 1.0 if direction == "long" else -1.0
    gross_points = sign * (exit_price - entry_price)
    gross_dollars = gross_points * POINT_VALUE
    return gross_dollars - round_trip_commission
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Strategy logic re-derived inside a monolithic backtest run | Artifact-driven phases with explicit parquet handoff | Already established in Phases 2-4 | Phase 5 should consume artifacts, not fold Phase 4 back into itself. |
| Mid/trade-based optimistic fills | BBO-side execution with optional extra impact | Common current best practice for top-of-book historical replay | Better cost realism without pretending to model depth. |
| Heavy backtesting framework adoption | Custom numeric pipeline plus small sequential state loop | Current repo direction and modern data-tooling preference | Lower complexity and tighter alignment with the repo's deterministic pipeline. |

**Deprecated/outdated:**
- Generic framework-first design for this repo: it conflicts with the established phase artifact pattern and adds abstractions the codebase does not currently use.
- Same-bar optimistic execution: 1-second BBO data does not justify favorable intrabar assumptions.

## Open Questions

1. **What default round-trip commission should Phase 5 ship with?**
   - What we know: IBKR publicly lists `USD 0.85/contract` commission for U.S. futures before exchange/regulatory fees, and Tradovate publicly lists `USD 0.99/standard contract per side` commission before exchange, clearing, and NFA fees.
   - What's unclear: the exact all-in prop-like baseline the user wants for NQ in this repo.
   - Recommendation: default to `USD 5.00` round trip per contract, expose it as a CLI/config parameter, and document it as a baseline assumption rather than a universal truth.

2. **How should same-second target/stop collisions be handled?**
   - What we know: 1-second top-of-book snapshots do not reveal within-second ordering.
   - What's unclear: whether the user prefers conservative or neutral tie-break handling.
   - Recommendation: implement adverse-first precedence and record that policy in the artifact metadata and tests.

3. **How should the plan treat the wording conflict in `TSIM-01`?**
   - What we know: `REQUIREMENTS.md` still mentions post-failure confirmation, but the locked Phase 5 context explicitly says immediate entry on setup event.
   - What's unclear: whether the requirements file will be updated in a later housekeeping phase.
   - Recommendation: plan against the locked context now and note the requirement-text drift so future docs work can reconcile it.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime, CLI, tests | yes | 3.14.3 | none |
| Polars | Artifact loading/writing | yes | 1.39.2 | Use the repo pin range `>=1.39.3,<1.40` when refreshing env |
| PyArrow | Parquet IO | yes | 23.0.1 | none |
| NumPy | Numeric helpers | yes | 2.4.4 local | Keep repo pin unless dependency work is explicitly added |
| pytest module | Validation | yes | 8.4.2 | Use `python -m pytest` |
| `pytest` CLI on `PATH` | Convenience only | no | none | `python -m pytest` |

**Missing dependencies with no fallback:**
- None for planning. The local environment can execute the phase using `python -m pytest`.

**Missing dependencies with fallback:**
- Bare `pytest` shell command is missing from `PATH`; use `python -m pytest` instead.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 locally, repo dev pin `>=9.0.2,<10` |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/indicators/test_trade_simulation.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TSIM-01 | Immediate entry from Phase 4 event row using setup direction | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_enters_immediately_from_setup_event -x` | no - Wave 0 |
| TSIM-02 | Exits on daily VWAP target using executable quote side | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_vwap_target_uses_executable_quote_side -x` | no - Wave 0 |
| TSIM-03 | Bid/ask spread-crossing cost plus configurable extra impact | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_fill_prices_apply_bbo_side_and_additional_impact -x` | no - Wave 0 |
| TSIM-04 | Round-trip commissions deducted from net P&L | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_round_trip_commission_reduces_net_pnl -x` | no - Wave 0 |
| TSIM-05 | One active trade blocks overlapping setups | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_overlapping_setups_are_skipped_while_position_active -x` | no - Wave 0 |
| TSIM-07 | Fixed-point MAE stop closes trade conservatively | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_stop_loss_uses_executable_mae_and_adverse_first_ordering -x` | no - Wave 0 |
| TSIM-08 | Force-close at 16:00 ET if still open | unit | `python -m pytest tests/indicators/test_trade_simulation.py::test_session_end_forces_exit_at_1600_et -x` | no - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/indicators/test_trade_simulation.py -x`
- **Per wave merge:** `python -m pytest tests/indicators/test_trade_simulation.py tests/indicators/test_trade_simulation_validation.py -x`
- **Phase gate:** `python -m pytest`

### Wave 0 Gaps
- [ ] `tests/indicators/test_trade_simulation.py` - core replay behavior and cost model for `TSIM-01/02/03/04/05/07/08`
- [ ] `tests/indicators/test_trade_simulation_validation.py` - artifact writer and CLI command coverage for Phase 5 outputs
- [ ] CLI coverage for `build-phase5-trade-simulation` with the same style parity already used in `src/vwap_revert/cli.py`

## Sources

### Primary (HIGH confidence)
- Existing project context: `.planning/phases/05-trade-simulation-engine/05-CONTEXT.md` - locked decisions, scope, and deferred ideas
- Existing project implementation: `src/vwap_revert/indicators/setup_detection.py` - canonical setup log and enriched artifact pattern
- Existing project implementation: `src/vwap_revert/indicators/vwap.py` - row-aligned indicator attachment and parquet-writing pattern
- Existing project implementation: `src/vwap_revert/cli.py` - phase-builder CLI style
- Existing project tests: `tests/indicators/test_setup_detection.py`, `tests/indicators/test_setup_detection_validation.py` - current testing convention for phase modules and CLI outputs
- CME Group NQ product page: https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html - contract multiplier and minimum tick
- Polars documentation: https://docs.pola.rs/ - DataFrame/parquet APIs used by the repo
- PyPI Polars release history: https://pypi.org/project/polars/ - current visible 1.39.x release line
- PyPI PyArrow release history: https://pypi.org/project/pyarrow/ - current visible `23.0.1`
- PyPI pytest release history: https://pypi.org/pypi/pytest/ - current visible `9.0.2`

### Secondary (MEDIUM confidence)
- Interactive Brokers futures commissions: https://www.interactivebrokers.com/en/pricing/commissions-futures.php?re=amerx - commission component for U.S. futures before exchange/regulatory fees
- Tradovate pricing: https://www.tradovate.com/ - standard-contract per-side commission component before exchange, clearing, and NFA fees

### Tertiary (LOW confidence)
- All-in `USD 5.00` round-trip commission baseline - inference from public broker commission components plus typical exchange/clearing/NFA fees, not a universal official standard
- Adverse-first same-row tie-break - conservative execution-policy recommendation, not an externally documented exchange rule

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - it follows the repo's current stack and current official package release histories.
- Architecture: HIGH - it extends existing phase-artifact and CLI patterns without introducing a new framework.
- Pitfalls: MEDIUM - executable-side fill logic is clear, but commission defaults and same-row path ordering require explicit planner choices.

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
