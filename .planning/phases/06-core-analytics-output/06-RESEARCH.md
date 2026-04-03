# Phase 6: Core Analytics & Output - Research

**Researched:** 2026-04-02
**Domain:** Trade-level analytics, performance metrics, and deterministic export artifacts
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Analytics input contract
- **D-01:** Treat the Phase 5 trade log parquet as the canonical input for Phase 6 analytics rather than replaying trades again or recomputing Phase 4/5 logic inside the analytics layer.
- **D-02:** Preserve one row per completed trade and keep the Phase 5 context columns (`setup_sigma_signed`, `nearest_structural_level`, `regime_label`, `regime_reason`) in the analytics-ready trade log so later phases can segment results without schema churn.
- **D-03:** Fill the roadmap-required trade-log fields by deriving missing analysis columns from existing Phase 5 economics, especially converting point P&L into ticks while retaining net dollar P&L as the primary cost-aware measure.

### Metric definitions
- **D-04:** Compute the baseline performance metrics from completed trades only: win rate, average win/loss ratio, profit factor, max drawdown, Sharpe ratio, and total P&L.
- **D-05:** Use `net_dollars` as the default economic basis for aggregate performance metrics so commissions remain included, while also surfacing point/tick-level trade fields for inspection.
- **D-06:** Keep metric formulas deterministic and explicit, including documented handling for edge cases such as zero losses, zero variance, or too few trades for a stable Sharpe estimate.

### Output surfaces
- **D-07:** Emit both machine-readable summary artifacts and analyst-friendly tabular exports from the same Phase 5 input snapshot so CSV and JSON stay numerically aligned.
- **D-08:** Export the enriched trade log to CSV for spreadsheet-style review and export aggregate metrics to JSON for downstream scripting, while allowing additional companion files if they improve auditability.
- **D-09:** Follow the established per-phase artifact pattern: deterministic filenames, explicit manifests/metadata where useful, and validation exports keyed by selected dates or runs instead of ad hoc notebook-only analysis.

### CLI and workflow integration
- **D-10:** Add a dedicated Phase 6 builder command alongside the existing phase commands instead of hiding analytics behind a test helper or notebook-only path.
- **D-11:** Phase 6 should consume Phase 5 output directories directly, produce a self-contained analytics output directory, and avoid mutating upstream artifacts in place.
- **D-12:** Keep the analytics schema Phase 9/10-friendly by exposing enough trade-level detail now that future regime, sigma-band, and time-of-day breakdowns can layer on without reworking the baseline exports.

### the agent's Discretion
- Exact file names for the Phase 6 CSV/JSON artifacts, as long as they are deterministic and clearly phase-scoped.
- Precise Sharpe scaling convention and null policy, as long as it is documented and consistent.
- Additional summary metrics or diagnostics beyond the roadmap minimum, as long as they do not distract from the required Phase 6 contract.

### Deferred Ideas (OUT OF SCOPE)
- Regime, sigma-band, and time-of-day breakdowns belong to Phase 10, not the baseline Phase 6 metrics pass.
- Weekly VWAP, monthly VWAP, and developing POC target comparisons belong to later phases once those anchors exist.
- Continuation-failure refinements and multi-target management remain Phase 9 work, not analytics responsibilities.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ANLY-01 | System produces trade log with entry price, exit price, P&L (ticks and dollars), duration, sigma at entry, structural level, regime | Extend the Phase 5 trade parquet with deterministic derived columns such as `gross_ticks`, `net_ticks`, and explicit duration fields, while preserving the carried context columns untouched. |
| ANLY-02 | System computes core performance metrics - win rate, average win/loss, profit factor, max drawdown, Sharpe ratio, total P&L | Compute all six metrics from completed trades using `net_dollars` as the aggregate economic basis, with documented null/zero handling for empty, all-win, all-loss, and zero-variance cases. |
| ANLY-03 | System outputs results to structured CSV and JSON files | Emit a deterministic trade-log CSV plus metrics JSON from the same enriched DataFrame snapshot, with a manifest and optional validation export following the repo's existing artifact pattern. |
</phase_requirements>

## Summary

Phase 6 should stay as a thin analytics layer over the finished Phase 5 trade log. It should not replay fills, touch Phase 4 setup rows, or introduce a third economic representation. The canonical flow is: read `phase5_trade_log.parquet`, derive the small set of missing analysis columns once, compute aggregate metrics from that enriched trade-level frame, then write deterministic artifacts.

The repo's existing pattern is already clear: every phase consumes the previous phase's output directory, writes a self-contained output directory, and emits validation artifacts with explicit manifests. Phase 6 should preserve that pattern rather than adding notebook-only analysis or a heavyweight analytics dependency. Polars and NumPy are sufficient for the required trade-log enrichment, cumulative-P&L/drawdown math, and Sharpe calculation.

The main planning risk is not complexity; it is metric-definition drift. The plan should lock exact formulas, edge-case behavior, and filenames up front so CSV, JSON, validation exports, and future Phase 10 breakdowns all derive from the same trade-level truth.

**Primary recommendation:** Build a `build-phase6-analytics` command that reads the Phase 5 parquet trade log, writes an enriched Phase 6 trade log CSV, computes six baseline metrics from `net_dollars`, and emits a manifest-backed JSON summary plus a small validation export.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.3 local | Runtime and CLI entrypoint | Already required by the repo and available locally. |
| Polars | 1.39.3 current; 1.39.2 local | Read Phase 5 parquet, derive columns, sort chronologically, write CSV | Already the repo's tabular engine and official docs directly cover the needed APIs. |
| NumPy | 2.4.4 local; 2.4.3 visible on PyPI | Sharpe/std-dev math and numeric helpers | Already pinned by the repo and installed locally; public package metadata lags the local pin. |
| PyArrow | 23.0.1 | Parquet IO compatibility | Matches the repo pin and local environment. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 current; 8.4.2 local | Unit and CLI validation | Use `python -m pytest` in this workspace because the module is available even though environment pins lag. |
| json / pathlib / dataclasses | stdlib | Metrics artifact writing, paths, config | Use for manifest/summary serialization and CLI wiring. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Polars + NumPy + stdlib | pandas + empyrical/quantstats | Adds dependencies and conventions the repo does not currently use for only six simple metrics. |
| CSV + JSON from one enriched frame | Separate notebook analysis and ad hoc exports | Breaks determinism and increases the chance of metric drift across outputs. |
| Companion parquet mirror of Phase 6 trade log | CSV only | CSV satisfies the requirement, but parquet remains safer for downstream typed consumption if the planner wants a canonical companion artifact. |

**Installation:**
```bash
python -m pip install -e .[dev]
```

**Version verification:**
- `polars 1.39.3` is the current PyPI release with upload date `2026-03-20`; the local environment currently has `1.39.2`.
- `pyarrow 23.0.1` is the current PyPI release with release date `2026-02-16`; the local environment matches it.
- `numpy` is an environment anomaly: the repo pin and local environment report `2.4.4`, while current public PyPI results still show `2.4.3` dated `2026-03-09`. Treat the repo pin as authoritative for this phase unless dependency work is explicitly added.
- `pytest 9.0.2` is the current PyPI release with release date `2025-12-06`; the local environment currently has `8.4.2`.

## Architecture Patterns

### Recommended Project Structure
```text
src/
`-- vwap_revert/
    |-- analytics.py        # Phase 6 trade-log enrichment, metrics, artifact writers
    `-- cli.py             # add build-phase6-analytics
tests/
`-- indicators/
    |-- test_core_analytics.py
    `-- test_core_analytics_validation.py
```

### Pattern 1: Phase 5 Trade Parquet Is the Only Input
**What:** Read the Phase 5 trade log parquet directly and do all Phase 6 work from that single artifact.
**When to use:** Always for this phase.
**Why:** It honors `D-01`, prevents replay drift, and preserves the established artifact boundary.
**Example:**
```python
# Source: project pattern from src/vwap_revert/simulation.py
trade_log = pl.read_parquet(phase5_root / "phase5_trade_log.parquet").sort(["trading_date", "entry_ts"])
```

### Pattern 2: Enrich Once, Reuse Everywhere
**What:** Add all missing analysis columns in one deterministic transformation, then feed both exports and metrics from that same frame.
**When to use:** Before any CSV/JSON writing.
**Why:** It keeps the CSV and JSON numerically aligned per `D-07`.
**Example:**
```python
# Source: Phase 6 research recommendation based on the existing artifact flow
analytics_log = trade_log.with_columns(
    (pl.col("gross_points") / pl.lit(0.25)).alias("gross_ticks"),
    (pl.col("net_dollars") / pl.lit(5.0)).alias("net_ticks"),
    (pl.col("duration_seconds") / pl.lit(60.0)).alias("duration_minutes"),
    pl.col("setup_sigma_signed").alias("sigma_at_entry"),
)
```

### Pattern 3: Aggregate Metrics From `net_dollars`
**What:** Use `net_dollars` for all baseline performance metrics and keep point/tick fields as descriptive trade-level columns.
**When to use:** Win rate, average win/loss ratio, profit factor, drawdown, Sharpe, total P&L.
**Why:** This is the locked economic basis in `D-05`.
**Example:**
```python
# Source: project decision D-05
wins = analytics_log.filter(pl.col("net_dollars") > 0)
losses = analytics_log.filter(pl.col("net_dollars") < 0)
total_pnl = float(analytics_log["net_dollars"].sum())
win_rate = wins.height / analytics_log.height if analytics_log.height else None
```

### Pattern 4: Drawdown From Chronological Equity Curve
**What:** Build cumulative net P&L in entry order, then compute drawdown as equity minus running peak.
**When to use:** `max_drawdown`.
**Why:** It is simple, deterministic, and does not require a portfolio analytics library.
**Example:**
```python
# Source: standard cumulative-P&L pattern implemented with Polars
equity = analytics_log.select(
    pl.col("entry_ts"),
    pl.col("net_dollars").cum_sum().alias("cum_net_dollars"),
).with_columns(
    pl.col("cum_net_dollars").cum_max().alias("running_peak"),
).with_columns(
    (pl.col("cum_net_dollars") - pl.col("running_peak")).alias("drawdown_dollars"),
)
max_drawdown = abs(float(equity["drawdown_dollars"].min())) if equity.height else 0.0
```

### Pattern 5: Follow the Existing Validation/Manifest Style
**What:** Write required outputs plus a small validation CSV and `validation_sessions.json` manifest.
**When to use:** Every deterministic phase builder in this repo.
**Why:** It matches Phases 2-5 and keeps manual inspection simple.
**Example:**
```python
# Source: project artifact pattern from src/vwap_revert/simulation.py
validation_export = analytics_log.filter(pl.col("trading_date").cast(pl.Utf8).is_in(validation_dates))
validation_export.write_csv(output_root / "validation" / "analytics_validation_export.csv")
```

### Anti-Patterns to Avoid
- **Recomputing Phase 4 or 5 logic inside analytics:** It breaks the canonical boundary and invites drift.
- **Using different frames for CSV and JSON:** This can produce mismatched numbers for the same run.
- **Treating metric edge cases implicitly:** `inf`, `NaN`, and empty-frame behavior should be explicit in the contract.
- **Adding a heavyweight analytics framework:** The required metrics are too small to justify stack churn.
- **Building notebook-only analysis paths:** The roadmap requires deterministic file outputs and CLI wiring.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| New analytics framework | Portfolio/reporting abstraction layer | Polars transforms + NumPy/stdlib math | Only six metrics are required and the repo already uses Polars everywhere. |
| Separate serializer logic for each output | Divergent CSV and JSON code paths | One enriched trade DataFrame feeding all artifacts | Prevents schema and numeric drift. |
| Custom parquet reader pipeline | Manual file scanning or replay walk | `pl.read_parquet(...)` on the Phase 5 artifact | The repo already persists a single canonical Phase 5 trade parquet. |
| Fancy risk metrics package | pyfolio/quantstats-style dependency set | Explicit local formulas for the six required metrics | Dependency cost is not justified for the MVP analytics scope. |
| Ad hoc validation sampling | Manual notebooks | Deterministic validation export keyed by `--validation-date` | Matches the established repo pattern and is easier to review. |

**Key insight:** Phase 6 is not a research notebook phase. It is an artifact-contract phase. The planner should optimize for deterministic schemas and explicit formulas, not analytic breadth.

## Common Pitfalls

### Pitfall 1: Tick P&L Is Derived Inconsistently
**What goes wrong:** Trade-level tick columns disagree with dollar metrics because one is based on gross points and the other on net dollars.
**Why it happens:** The code mixes pre-cost and post-cost representations without naming them clearly.
**How to avoid:** Keep `net_dollars` as the primary aggregate basis, and name derived tick fields explicitly, e.g. `gross_ticks` and `net_ticks`.
**Warning signs:** A winning trade in points appears negative in dollars with no clear explanation in the schema.

### Pitfall 2: Max Drawdown Is Computed On Unsorted Trades
**What goes wrong:** Drawdown changes when the same trade log is shuffled.
**Why it happens:** Cumulative P&L is calculated without enforcing chronological order.
**How to avoid:** Sort by `entry_ts` before any cumulative-equity math.
**Warning signs:** `max_drawdown` changes after CSV reloads or minor upstream ordering changes.

### Pitfall 3: Zero-Loss Cases Produce Unusable JSON
**What goes wrong:** Profit factor or average win/loss ratio becomes `Infinity` or `NaN`, which is awkward for downstream consumers.
**Why it happens:** Edge-case behavior is left to floating-point defaults.
**How to avoid:** Choose a documented null policy up front. Recommended: emit `null` for undefined ratios and Sharpe, while keeping `total_pnl` and `max_drawdown` numeric.
**Warning signs:** JSON serialization contains non-standard values or downstream parsing fails.

### Pitfall 4: Sharpe Ratio Looks Precise But Is Not Stable
**What goes wrong:** A tiny sample or zero-variance sample yields a misleading Sharpe.
**Why it happens:** The code applies a formula mechanically without checking sample size or standard deviation.
**How to avoid:** Require at least two trades and non-zero sample standard deviation; otherwise emit `null`.
**Warning signs:** Very small runs show extreme or undefined Sharpe values.

### Pitfall 5: Phase 6 Mutates or Copies Upstream Artifacts In Place
**What goes wrong:** Re-running analytics changes Phase 5 files or blurs which phase owns which schema.
**Why it happens:** Output directories are treated as shared workspaces instead of immutable phase handoffs.
**How to avoid:** Consume `phase5_root` read-only and always write to a new `output_root`.
**Warning signs:** Phase 5 artifact timestamps change after a Phase 6 run.

## Code Examples

Verified project-aligned patterns:

### Trade-Log Enrichment
```python
# Source: project artifact pattern + Phase 6 research recommendation
from dataclasses import dataclass
from pathlib import Path

import polars as pl


@dataclass(frozen=True)
class AnalyticsConfig:
    tick_size: float = 0.25
    tick_value: float = 5.0
    sharpe_scale: float = 1.0


def build_analytics_trade_log(phase5_root: Path, config: AnalyticsConfig) -> pl.DataFrame:
    trade_log = pl.read_parquet(phase5_root / "phase5_trade_log.parquet").sort(["trading_date", "entry_ts"])
    return trade_log.with_columns(
        (pl.col("gross_points") / pl.lit(config.tick_size)).alias("gross_ticks"),
        (pl.col("net_dollars") / pl.lit(config.tick_value)).alias("net_ticks"),
        (pl.col("duration_seconds") / pl.lit(60.0)).alias("duration_minutes"),
        pl.col("setup_sigma_signed").alias("sigma_at_entry"),
    )
```

### Baseline Metrics
```python
# Source: Phase 6 research recommendation using net_dollars as the aggregate basis
import math
import numpy as np


def compute_metrics(net_results: list[float], sharpe_scale: float = 1.0) -> dict[str, float | None]:
    trade_count = len(net_results)
    wins = [x for x in net_results if x > 0]
    losses = [x for x in net_results if x < 0]

    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = abs(sum(losses) / len(losses)) if losses else None
    profit_factor = (sum(wins) / abs(sum(losses))) if losses else None
    win_loss_ratio = (avg_win / avg_loss) if (avg_win is not None and avg_loss not in (None, 0.0)) else None

    sharpe = None
    if trade_count >= 2:
        sample_std = float(np.std(net_results, ddof=1))
        if sample_std > 0.0:
            sharpe = float(np.mean(net_results) / sample_std) * sharpe_scale

    return {
        "trade_count": trade_count,
        "win_rate": (len(wins) / trade_count) if trade_count else None,
        "average_win_loss_ratio": win_loss_ratio,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "total_pnl": float(sum(net_results)),
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Notebook-only backtest analysis | CLI-built deterministic analytics artifacts | Already established by the repo's Phases 2-5 pattern | Keeps outputs reproducible and planner-friendly. |
| CSV-only research exports | Mixed typed source artifact + analyst-facing CSV/JSON surfaces | Common current pattern in data pipelines | Balances downstream scripting with easy human inspection. |
| Framework-first analytics stacks | Lean dataframe-first pipelines | Current repo direction and broader Python data-tooling norm | Lower complexity and tighter alignment with the existing codebase. |

**Deprecated/outdated:**
- Replaying trades inside analytics: the Phase 5 parquet already encodes the executed economics and should remain the source of truth.
- Implicit `NaN`/`inf` finance metrics: structured outputs should use explicit null policies instead.

## Open Questions

1. **What Sharpe scaling should Phase 6 expose?**
   - What we know: the phase context leaves the precise scaling convention to agent discretion.
   - What's unclear: whether the user wants per-trade Sharpe (`1.0` scaling), daily-equivalent scaling, or another convention.
   - Recommendation: default to per-trade Sharpe with `sharpe_scale=1.0` for MVP determinism, document it, and keep the scale configurable for later refinement.

2. **Should Phase 6 write a companion parquet trade log?**
   - What we know: `ANLY-03` only requires structured CSV and JSON, but `D-08` permits companion files.
   - What's unclear: whether the planner prefers strict minimum artifacts or a typed Phase 6 canonical handoff for later phases.
   - Recommendation: make CSV and JSON mandatory; treat parquet as optional if the planner wants a stronger downstream contract.

3. **How should undefined ratios serialize?**
   - What we know: `D-06` requires deterministic handling for zero losses, zero variance, and too-few-trades cases.
   - What's unclear: whether the user prefers `null`, sentinel strings, or omitted keys.
   - Recommendation: keep keys present and use JSON `null` for undefined `average_win_loss_ratio`, `profit_factor`, and `sharpe_ratio`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime, CLI, tests | yes | 3.14.3 | none |
| Polars | Trade-log enrichment and CSV export | yes | 1.39.2 local | Keep Phase 6 within already-used APIs or align env to repo pin `>=1.39.3,<1.40` |
| PyArrow | Parquet input | yes | 23.0.1 | none |
| NumPy | Sharpe/std-dev math | yes | 2.4.4 | Could compute std manually, but NumPy is already installed |
| pytest module | Validation | yes | 8.4.2 | Use `python -m pytest` |
| `pytest` executable on `PATH` | Convenience only | no | - | `python -m pytest` |

**Missing dependencies with no fallback:**
- None for planning. The environment can support a straightforward Phase 6 implementation.

**Missing dependencies with fallback:**
- Bare `pytest` shell command is not available on `PATH`; use `python -m pytest`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 local, repo dev pin `>=9.0.2,<10` |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/indicators/test_core_analytics.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ANLY-01 | Phase 5 trades enrich into a one-row-per-trade analytics log with required price, duration, sigma, structural, regime, and tick/dollar fields | unit | `python -m pytest tests/indicators/test_core_analytics.py::test_build_analytics_trade_log_adds_required_fields -x` | no - Wave 0 |
| ANLY-02 | Metrics are computed from completed trades using deterministic edge-case handling | unit | `python -m pytest tests/indicators/test_core_analytics.py::test_compute_metrics_handles_required_baseline_cases -x` | no - Wave 0 |
| ANLY-03 | CLI writes deterministic CSV/JSON/validation artifacts from a Phase 5 output directory | integration | `python -m pytest tests/indicators/test_core_analytics_validation.py::test_cli_writes_phase6_analytics_artifacts -x` | no - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/indicators/test_core_analytics.py -x`
- **Per wave merge:** `python -m pytest tests/indicators/test_core_analytics.py tests/indicators/test_core_analytics_validation.py -x`
- **Phase gate:** `python -m pytest`

### Wave 0 Gaps
- [ ] `tests/indicators/test_core_analytics.py` - trade-log enrichment and metric-definition coverage for `ANLY-01` and `ANLY-02`
- [ ] `tests/indicators/test_core_analytics_validation.py` - artifact writer and CLI coverage for `ANLY-03`
- [ ] `src/vwap_revert/analytics.py` - dedicated Phase 6 module to keep analytics separate from Phase 5 replay logic

## Sources

### Primary (HIGH confidence)
- Existing project context: `.planning/phases/06-core-analytics-output/06-CONTEXT.md` - locked decisions, scope, and deferred work
- Existing project requirements: `.planning/REQUIREMENTS.md` - `ANLY-01`, `ANLY-02`, `ANLY-03`
- Existing project state: `.planning/STATE.md` - current stack and phase handoff status
- Existing implementation: `src/vwap_revert/simulation.py` - canonical Phase 5 trade-log schema and artifact-writing pattern
- Existing implementation: `src/vwap_revert/cli.py` - phase builder CLI pattern and validation-date handling
- Existing tests: `tests/indicators/test_trade_simulation.py`, `tests/indicators/test_trade_simulation_validation.py` - current testing conventions for artifact-producing phases
- Polars `DataFrame.write_csv` docs: https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_csv.html - CSV export contract and formatting options
- Polars `DataFrame.write_json` docs: https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_json.html - JSON export contract
- Polars `read_parquet` docs: https://docs.pola.rs/api/python/stable/reference/api/polars.read_parquet.html - parquet input semantics and the eager/lazy guidance
- Polars PyPI page: https://pypi.org/project/polars/ - current version `1.39.3`, uploaded `2026-03-20`
- NumPy PyPI page: https://pypi.org/project/numpy/ - current public results show `2.4.3`, released `2026-03-09`
- PyArrow PyPI page: https://pypi.org/project/pyarrow/ - current version `23.0.1`, released `2026-02-16`
- pytest PyPI page: https://pypi.org/project/pytest/ - current version `9.0.2`, released `2025-12-06`

### Secondary (MEDIUM confidence)
- CME Group NQ product page: https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.settlements.html - confirms the E-mini Nasdaq-100 contract is `$20 x index` with `0.25` minimum tick, supporting the existing point/tick conversions

### Tertiary (LOW confidence)
- Recommended null policy for undefined ratios and Sharpe - implementation recommendation inferred from downstream interoperability needs, not a documented external standard
- Recommended default Sharpe scaling of `1.0` - project-fit recommendation because the context leaves the exact convention open

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - it matches the current repo stack and was verified against official package pages and Polars docs.
- Architecture: HIGH - it directly extends the repo's existing phase-artifact and CLI patterns.
- Pitfalls: HIGH - they are grounded in the locked phase decisions and the current Phase 5 artifact contract.

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
