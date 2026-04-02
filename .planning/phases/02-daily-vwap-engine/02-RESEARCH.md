# Phase 2: Daily VWAP Engine - Research

**Researched:** 2026-04-02
**Domain:** Session-anchored futures VWAP, volume-weighted expanding sigma bands, and manual chart validation
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Session anchor and reset policy
- **D-01:** Anchor the daily VWAP and sigma calculations to the regular trading hours open at 9:30 AM America/New_York for each `trading_date`, not midnight UTC and not the 6:00 PM ET Globex open.
- **D-02:** Compute the Phase 2 indicator from RTH-only trade flow so the VWAP reference matches the strategy's early-session reversion lens and can be cross-validated against an RTH session VWAP on charting platforms.
- **D-03:** Treat the first eligible RTH trade of each session as the initial VWAP observation; before that trade arrives, indicator values may remain null within the session rather than synthesizing a pre-trade anchor.

### Price and volume inputs
- **D-04:** Use actual trade-print rows only (`side` in `B` or `A`) as VWAP inputs, with `price * size` and `size` as the cumulative numerators/denominator.
- **D-05:** Do not use BBO mid-price rows as synthetic trade inputs for Phase 2; when no trade occurs in a given second, carry the most recent VWAP and sigma values forward instead of imputing volume.
- **D-06:** Base indicator ordering and session membership on the Phase 1 canonical session-labeled dataset so DST handling and contract selection remain inherited, not reimplemented inside the VWAP engine.

### Sigma-band methodology
- **D-07:** Implement sigma as the volume-weighted expanding standard deviation from the same session anchor using cumulative `sum(volume * price^2)`, `sum(volume * price)`, and `sum(volume)`, never a rolling-window standard deviation.
- **D-08:** Publish 1 sigma through 4 sigma upper and lower bands from the computed session VWAP and expanding sigma so later phases can use the exact same columns for signal detection.
- **D-09:** Preserve strict causality: each row's VWAP and sigma may use only observations at or before that row's timestamp, with no full-session replay or future leakage.

### Output and validation surface
- **D-10:** Materialize the Phase 2 output as a reusable indicator dataset keyed to the canonical Phase 1 timeseries, with VWAP and band columns aligned row-for-row so later phases can join by existing timestamps without additional reshaping.
- **D-11:** Produce a cross-validation artifact for manually checked sessions that records timestamped VWAP and sigma-band values in a side-by-side friendly format for TradingView or NinjaTrader comparisons.
- **D-12:** Validate on at least five manually chosen sessions spanning ordinary days and DST-adjacent periods, and treat a mismatch beyond 0.25 NQ points as a blocking defect for Phase 2 completion.

### the agent's Discretion
- Exact module names and package boundaries for the new indicator code.
- Persistence layout for reusable outputs and validation artifacts.
- Exact schema of the manual comparison export.

### Deferred Ideas (OUT OF SCOPE)
- Overnight-inclusive daily VWAP variants for sensitivity analysis.
- Weekly and monthly VWAP handling across contract rolls.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VWAP-01 | System computes Daily VWAP from trade prints using price × volume weighting | Filter to RTH trade rows only, then compute cumulative `sum(price * size) / sum(size)` per `trading_date`. |
| VWAP-02 | System computes volume-weighted expanding standard deviation bands (1σ through 4σ) | Maintain cumulative `sum(v*p^2)`, derive variance as `sum(v*p^2)/sum(v) - vwap^2`, clamp negative float noise to zero, then emit upper/lower bands. |
| VWAP-06 | System outputs VWAP values for side-by-side chart validation | Persist a deterministic comparison artifact for at least five sessions with timestamp, trade price, VWAP, sigma, and 1σ-4σ band columns. |
</phase_requirements>

## Summary

Phase 2 is a correctness-first indicator phase. The stack and earlier project research already settle the big architectural question: keep the implementation inside the existing Polars-first package, but do the actual cumulative VWAP math with explicit formulas rather than generic rolling helpers. The highest-risk failure mode is not speed, it is quietly computing the wrong sigma series.

The practical implementation path is to treat the Phase 1 canonical cache as the only source of truth, derive an RTH trade-only working frame, compute session-causal cumulative arrays, then join the resulting indicator columns back onto the broader session timeseries so later phases inherit a row-aligned dataset. When there is no new trade in a second, the indicator should simply hold its previous value; that matches the trade-only definition and keeps quote-only rows usable for downstream signal alignment.

**Primary recommendation:** Split Phase 2 into one plan for the reusable indicator engine plus automated math tests, and one plan for output surfaces: a persisted indicator artifact, a CLI entrypoint, and a manual cross-validation export covering at least five sessions.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Polars | existing project dependency | Session filtering, joins, parquet reads/writes | Matches the existing codebase and handles row-aligned dataset transforms cleanly. |
| NumPy | existing project dependency | Fast cumulative math for VWAP and variance arrays | Best fit for explicit `cumsum`-style formulas and floating-point control. |
| pytest | existing project dev dependency | Unit and integration coverage | Needed to lock the unusual sigma math before execution phases build on it. |

### Supporting
| Library | Purpose | When to Use |
|---------|---------|-------------|
| `pathlib` | Output path management | Validation export and indicator artifact paths |
| `json` / `csv` | Validation artifact metadata | Recording manual comparison session manifests |
| existing CLI pattern in `src/vwap_revert/cli.py` | Phase command surface | Add Phase 2 build/export commands without inventing a new entrypoint style |

## Architecture Patterns

### Pattern 1: Trade-only working frame, row-aligned output frame
**What:** Compute VWAP from a filtered trade-only RTH frame, then left-join the results back onto the broader Phase 1 canonical frame and forward-fill within each `trading_date`.
**Why:** Preserves the mathematically correct trade-only definition while keeping quote rows and timestamps available for later phases.

### Pattern 2: Explicit cumulative variance identity
**What:** Use cumulative `sum(v*p)`, `sum(v*p^2)`, and `sum(v)` with:
```text
vwap = cum_vp / cum_v
variance = (cum_vp2 / cum_v) - vwap^2
sigma = sqrt(max(variance, 0))
```
**Why:** This is the locked formula from the project research and avoids both rolling-window mistakes and pandas precision issues.

### Pattern 3: Validation export is a first-class artifact
**What:** Write a comparison-friendly artifact for a fixed list of validation sessions instead of relying on ad hoc notebook inspection.
**Why:** VWAP-06 is a release gate, not a nice-to-have. The artifact must be reproducible enough for later reviewers to re-run or inspect.

### Anti-Patterns to Avoid
- Using `rolling().std()` or any windowed helper to derive sigma bands.
- Mixing overnight and RTH rows in the same daily anchor after D-02 locked RTH-only behavior.
- Treating quote mid-price as a VWAP input instead of a downstream price context only.
- Computing the full session indicator first and then replaying it row-by-row, which would introduce look-ahead bias.

## Common Pitfalls

### Pitfall 1: Wrong sigma formula dressed up as “close enough”
**What goes wrong:** A conventional rolling or unweighted expanding standard deviation gets substituted for the required volume-weighted expanding formula.
**How to avoid:** Unit test against hand-calculated fixtures that explicitly cover `sum(v*p^2)` and causal accumulation.

### Pitfall 2: Anchor drift at the session boundary
**What goes wrong:** The code begins accumulating from overnight rows or from 9:30 ET quote rows that have no trade.
**How to avoid:** Gate accumulation on both `is_rth` and `side in {"A","B"}`, and keep pre-first-trade rows null until the first eligible trade appears.

### Pitfall 3: Joining the indicator back incorrectly
**What goes wrong:** The VWAP result is computed correctly on trades but misaligned when merged back to the canonical dataset.
**How to avoid:** Join on the exact timestamp key used for structural ordering (`ts_recv`) plus `trading_date`, then forward-fill only within each session.

### Pitfall 4: Weak manual validation trail
**What goes wrong:** The code “looks good” but there is no reproducible export for TradingView or NinjaTrader comparison.
**How to avoid:** Bake the validation export and session manifest into the plan rather than leaving it as an afterthought.

## Code Examples

### Explicit cumulative VWAP and sigma
```python
cum_v = np.cumsum(volume)
cum_vp = np.cumsum(price * volume)
cum_vp2 = np.cumsum((price ** 2) * volume)

vwap = cum_vp / cum_v
variance = np.maximum(cum_vp2 / cum_v - np.square(vwap), 0.0)
sigma = np.sqrt(variance)
```

### Join-back pattern
```python
indicator_rows = trade_rows.select(
    "ts_recv",
    "trading_date",
    "daily_vwap",
    "daily_sigma",
)

enriched = (
    session_df.join(indicator_rows, on=["ts_recv", "trading_date"], how="left")
    .with_columns(
        pl.col("daily_vwap").forward_fill().over("trading_date"),
        pl.col("daily_sigma").forward_fill().over("trading_date"),
    )
)
```

## Environment Availability

| Dependency | Required By | Available | Notes |
|------------|------------|-----------|-------|
| Phase 1 canonical parquet cache helpers | Phase 2 load path | yes | `scan_canonical_cache()` already exists in `src/vwap_revert/data_pipeline/cache.py` |
| Session labels and ET timestamps | Anchor logic | yes | `label_sessions()` and ET helpers already exist |
| NumPy / Polars / pytest | Computation and tests | yes in project config | Existing project stack covers the phase |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Quick run command | `python -m pytest tests/indicators/test_vwap.py -x` |
| Full suite command | `python -m pytest tests/indicators -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VWAP-01 | Daily trade-only RTH VWAP resets and accumulates correctly | unit | `python -m pytest tests/indicators/test_vwap.py::test_daily_vwap_uses_rth_trade_rows_only -x` | no - create in Phase 2 |
| VWAP-02 | Expanding volume-weighted sigma and 1σ-4σ bands match hand-worked fixtures | unit | `python -m pytest tests/indicators/test_vwap.py::test_sigma_bands_use_volume_weighted_expanding_formula -x` | no - create in Phase 2 |
| VWAP-06 | Validation export writes the expected side-by-side columns and session manifest | integration | `python -m pytest tests/indicators/test_vwap_validation.py::test_validation_export_contains_comparison_columns -x` | no - create in Phase 2 |

## Sources

### Primary
- `.planning/phases/02-daily-vwap-engine/02-CONTEXT.md`
- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/PROJECT.md`
- `.planning/research/SUMMARY.md`
- `.planning/research/PITFALLS.md`
- `.planning/research/ARCHITECTURE.md`
- `.planning/research/STACK.md`

### Secondary
- Phase 1 code in `src/vwap_revert/data_pipeline/cache.py`, `src/vwap_revert/data_pipeline/sessions.py`, and `src/vwap_revert/cli.py`

## Metadata

**Confidence breakdown:**
- Indicator formula and causal model: HIGH
- Join/persistence shape: HIGH
- Manual platform comparison workflow: MEDIUM, because exact chart export formatting is a local design choice rather than a market standard

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
