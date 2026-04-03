# Phase 08: Regime & Multi-Timeframe VWAP - Research

**Researched:** 2026-04-03
**Domain:** Causal session-level volatility classification and roll-bridged weekly/monthly VWAP enrichment in a Polars-first futures pipeline
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### Regime classification contract
- **D-01:** Compute one realized-volatility summary per completed trading session from the canonical front-month dataset, using the existing `trading_date` order and only data available at or before that session close so later sessions can consume the value without look-ahead bias.
- **D-02:** Classify each active trading date causally from a rolling history of prior completed sessions rather than from same-day full-session volatility, so the label is already known when Phase 4/5 logic evaluates the early RTH window.
- **D-03:** Keep the initial regime model strictly binary and explicit: higher-volatility sessions map to `short_gamma`, lower-volatility sessions map to `long_gamma`, and the raw realized-volatility statistic plus threshold metadata should remain available for auditability.
- **D-04:** Use a deterministic rolling threshold rule instead of a hand-maintained calendar of regime dates, and treat insufficient lookback history as an explicit quality state rather than silently fabricating a regime label.

### Weekly and monthly VWAP semantics
- **D-05:** Reuse the Phase 2 daily-VWAP input policy for higher-timeframe anchors: RTH trade rows only, `price * size` weighting, no synthetic mid-price volume, and forward-filled row alignment within each trading date once the first eligible anchor trade exists.
- **D-06:** Reset weekly VWAP at the first eligible RTH trade of each ET trading week and monthly VWAP at the first eligible RTH trade of each ET calendar month, keyed from the existing Phase 1 `trading_date` semantics instead of re-deriving calendar logic inside a separate pipeline.
- **D-07:** Preserve strict causality for the higher-timeframe anchors exactly as in Phase 2: each row's weekly/monthly VWAP may only use trades at or before that row timestamp, and pre-anchor rows remain null rather than backfilled.
- **D-08:** Handle contract-roll discontinuities in weekly and monthly VWAP the same way Phase 7 handled HTF structural composites: align prior trade prices onto the active contract axis with deterministic completed-session roll deltas so anchors stay comparable across rolls instead of breaking at quarter boundaries.

### Output surface and downstream integration
- **D-09:** Materialize Phase 8 as a reusable row-aligned enriched parquet that appends regime columns and weekly/monthly VWAP columns onto the canonical timeseries without mutating upstream Phase 2 or Phase 7 artifacts in place.
- **D-10:** Also emit a compact session-level artifact that records per-session realized-volatility values, threshold inputs, final regime labels, and any quality/status fields so regime classification can be reviewed independently of the row-level dataset.
- **D-11:** Backfill the existing placeholder `regime_label` and `regime_reason` fields used by Phase 4/5/6 contracts, keeping column names stable so setup detection, simulation, and analytics can consume Phase 8 outputs without schema churn.
- **D-12:** Produce deterministic validation exports for selected dates that expose timestamped weekly/monthly VWAP values plus the session-level regime decision inputs, enabling manual chart comparison and spot-checks against the author's expected short-vs-long-gamma behavior.

### Claude's Discretion
- The exact realized-volatility formula and rolling lookback length, as long as the method is causal, documented, and stable enough for downstream research and validation.
- The precise thresholding mechanic for mapping realized volatility into binary `short_gamma` / `long_gamma` labels, as long as it stays deterministic and exposes enough metadata for auditability.
- Additional helper columns such as weekly/monthly anchor identifiers, regime percentile, or lookback coverage counts when they improve debugging without changing the Phase 8 contract.

### Deferred Ideas (OUT OF SCOPE)
- Regime-adjusted setup thresholds and selectivity tuning are consumed in later execution logic, not defined fully inside the baseline Phase 8 context capture.
- Continuation-failure detection, confluence scoring, and multi-target execution remain Phase 9 work.
- Regime/sigma/time-of-day breakdowns, equity-curve export, and comparison against the author's reference statistics remain Phase 10 work.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REGM-01 | System computes realized volatility over a configurable lookback window | Build one completed-session summary row per `trading_date`, compute a causal realized-vol statistic from prior completed sessions, and persist raw statistic plus lookback coverage. |
| REGM-02 | System classifies each session as short gamma or long gamma based on realized volatility thresholds | Use a deterministic rolling threshold from prior completed sessions, emit `regime_label`, `regime_reason`, threshold metadata, and explicit insufficient-history quality states. |
| REGM-03 | System applies regime-adjusted expectations (different deviation thresholds and selectivity per regime) | Phase 8 should provide stable regime metadata and threshold fields to downstream setup/simulation flows now; actual threshold tuning logic remains a later execution concern per locked deferred scope. |
| VWAP-04 | System computes Weekly VWAP rolling across sessions within the trading week | Reuse Phase 2 RTH-only trade-weighted cumulative VWAP logic with ISO-week anchor IDs, null-before-anchor policy, forward-fill within the active week, and Phase 7-style roll bridging. |
| VWAP-05 | System computes Monthly VWAP rolling across sessions within the calendar month | Reuse the same cumulative engine with calendar-month anchor IDs, null-before-anchor policy, forward-fill within the active month, and Phase 7-style roll bridging. |
</phase_requirements>

## Summary

Phase 8 should be planned as two tightly-coupled but separable outputs: a session-summary regime table and a row-aligned enriched parquet. The session table is the authoritative source for realized-volatility inputs, threshold decisions, and quality states; the row-level artifact is a pure join/carry-through surface that appends `weekly_vwap`, `monthly_vwap`, `regime_label`, `regime_reason`, and audit columns onto the canonical stream without changing existing Phase 2 or Phase 7 artifacts.

The implementation should not invent a second indicator framework. The repo already has the exact patterns needed: Phase 2 shows the causal cumulative VWAP and null-before-anchor behavior, while Phase 7 shows how to bridge completed prior-session prices onto the active contract axis across quarterly rolls. Extend those patterns directly. For regime classification, stay causal and session-based: compute one realized-vol statistic per completed session, classify the next session from rolling prior-session history, and treat insufficient history as a first-class status.

The main planning risk is not weekly/monthly VWAP math; it is the regime contract. There is no ground-truth gamma feed, and the roadmap requirement `REGM-03` is broader than the current locked Phase 8 scope. The safest plan is to make Phase 8 responsible for stable regime labels, metadata, and downstream compatibility, while explicitly deferring regime-specific setup threshold tuning to a later execution phase as required by the current context.

**Primary recommendation:** Build `indicators/regime.py` plus a new Phase 8 builder that first produces session-level causal regime metadata, then computes roll-bridged weekly/monthly VWAP on the row stream, then writes both artifacts and validation exports.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.14.3 local | Runtime | Already installed and supported by current local `pyarrow`/`pytest`; Phase 8 is DataFrame-heavy, not JIT-heavy. |
| Polars | 1.39.3 current on PyPI, 1.39.2 installed locally | Session summaries, cumulative VWAP, joins, forward-fill | Existing repo code is Polars-first and already uses `cum_sum().over(...)`, grouped joins, and date expressions successfully. |
| PyArrow | 23.0.1 | Parquet I/O | Existing artifact format and cache layer depend on Arrow-backed parquet. |
| NumPy | 2.4.4 local | Numeric fallback for validation math if needed | Already in the stack; useful for hand-checking realized-vol fixtures, but Phase 8 core can remain pure Polars. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `zoneinfo` | stdlib | ET semantics already resolved upstream | Reuse only through existing `trading_date`/`ts_recv_et`; do not re-derive sessions. |
| `tzdata` | 2025.3 | Windows timezone support | Needed indirectly by the existing session-label pipeline. |
| `pytest` | 9.0.2 pinned in `pyproject.toml`, 8.4.2 installed locally | Unit and CLI validation coverage | Use for Phase 8 core, artifact, and CLI regression tests; local environment should be reconciled with the pinned version. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing Polars cumulative expressions | Pandas resample/rolling logic | Slower, inconsistent with repo patterns, and more exposed to rolling-stat precision mistakes. |
| Deterministic rolling threshold from prior sessions | Hand-maintained regime date calendar | Easier to explain manually, but violates locked decisions and is brittle. |
| Phase 7-style roll delta bridging | Reset weekly/monthly VWAP at every contract roll | Simpler implementation, but breaks comparability mid-week/mid-month and contradicts D-08. |

**Version verification:** Verified current package references from local environment and PyPI on 2026-04-03.

| Package | Verified Version | Publish Date | Evidence |
|---------|------------------|--------------|----------|
| Polars | 1.39.3 | 2026-03-20 | PyPI release history |
| PyArrow | 23.0.1 | 2026-02-16 | PyPI release history |
| pytest | 9.0.2 | 2025-12-06 | PyPI release history |
| tzdata | 2025.3 | 2025-12-13 | PyPI release history |

## Architecture Patterns

### Recommended Project Structure
```text
src/
\-- vwap_revert/
    +-- indicators/
    |   +-- regime.py              # Session-level realized vol + regime decisions
    |   \-- vwap.py                # Extend or reuse helpers for weekly/monthly anchors
    +-- cli.py                     # New build-phase8-regime-vwap command
    \-- ...
```

### Pattern 1: Session-First Regime Pipeline
**What:** Build one completed-session summary row per `trading_date` before touching row-level regime columns.
**When to use:** Always for `REGM-01` and `REGM-02`.
**Example:**
```python
# Source: local repo pattern from src/vwap_revert/indicators/volume_profile.py
# Build per-session rows first, then join the active session metadata back to the row stream.
session_summary = (
    trade_rows
    .group_by("trading_date")
    .agg(
        pl.col("front_symbol").last().alias("front_symbol"),
        pl.col("price").last().alias("session_close_price"),
    )
    .sort("trading_date")
)
```

### Pattern 2: Anchor IDs From `trading_date`, Not From Raw Timestamps
**What:** Derive week/month anchor identifiers from the existing Phase 1 `trading_date` semantics.
**When to use:** Weekly/monthly VWAP resets and validation exports.
**Example:**
```python
# Source: Polars datetime docs for dt.iso_year, dt.week, dt.month_start
weekly_anchor = pl.struct(
    pl.col("trading_date").dt.iso_year().alias("iso_year"),
    pl.col("trading_date").dt.week().alias("iso_week"),
).alias("weekly_anchor_id")

monthly_anchor = pl.col("trading_date").dt.month_start().alias("monthly_anchor_id")
```

### Pattern 3: Roll-Bridge Before Cumulative Higher-Timeframe VWAP
**What:** Shift prior-session trade prices onto the active contract axis before cumulative weekly/monthly VWAP math.
**When to use:** Any week or month whose source sessions span more than one `front_symbol`.
**Example:**
```python
# Source: local repo pattern from src/vwap_revert/indicators/volume_profile.py
# Build deterministic completed-session boundary deltas, then add cumulative shift
# from source session -> target active session before cum_sum().over(anchor_id).
adjusted_price = pl.col("price") + pl.col("roll_bridge_shift")
```

### Pattern 4: Row-Aligned Artifact Plus Compact Summary Artifact
**What:** Persist both the row-level enriched parquet and the compact session-level regime summary.
**When to use:** Always; they serve different downstream consumers.
**Example:**
```python
# Source: local repo artifact pattern from Phase 2 and Phase 7
row_enriched.write_parquet(output_root / "phase8_regime_vwap_enriched.parquet")
session_summary.write_parquet(output_root / "phase8_session_regimes.parquet")
```

### Anti-Patterns to Avoid
- **Same-day full-session regime labels:** This leaks future volatility into the 9:30-11:30 ET decision window.
- **Independent calendar logic for week/month resets:** `trading_date` is already the canonical ET-aware session key.
- **Raw-price mixed-contract cumulative VWAP:** Weekly/monthly anchors become meaningless across quarter rolls without bridging.
- **Writing regime data only into Phase 4/5 outputs:** Phase 8 needs its own reusable enriched artifact, not ad hoc downstream mutations.
- **Treating `REGM-03` as a mandate to redesign Phase 4 thresholds now:** current locked context explicitly defers full selectivity tuning.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session/week/month boundary logic | A new calendar engine from raw UTC timestamps | Existing `trading_date` plus Polars date extractors | Repo already solved DST and session semantics in Phase 1. |
| Roll-spanning anchor continuity | Ad hoc per-row symbol switches or hard resets | Phase 7 completed-session roll delta pattern | The repo already proved this approach for mixed-roll HTF composites. |
| Regime transport to downstream artifacts | Custom schema rewrites in setup/simulation/analytics | Stable `regime_label` / `regime_reason` columns already present downstream | Avoids schema churn and keeps Phase 8 additive. |
| Validation surface | One-off notebook exports | Deterministic CSV + manifest alongside parquet artifacts | Matches every implemented phase and keeps manual checks reproducible. |

**Key insight:** The hard part of Phase 8 is cross-session state management. Reusing the repo's existing session, artifact, and roll-bridging machinery is materially safer than inventing a fresh implementation style.

## Common Pitfalls

### Pitfall 1: Weekly Keys Break at New Year
**What goes wrong:** Sessions at year boundaries get grouped into the wrong trading week.
**Why it happens:** Using calendar `year` with ISO `week` mixes incompatible systems.
**How to avoid:** Use `dt.iso_year()` with `dt.week()`, not `dt.year()` with `dt.week()`.
**Warning signs:** First trading days of January attach to the prior or wrong weekly VWAP.

### Pitfall 2: Regime Labels Leak Same-Day Information
**What goes wrong:** The regime label used during the early RTH window already includes same-day realized volatility.
**Why it happens:** Computing labels directly from full-session per-date volatility and joining them back by the same `trading_date`.
**How to avoid:** Shift the classification forward so session `T` uses thresholds/statistics built from completed sessions `< T`.
**Warning signs:** First valid session has a regime label despite no lookback history.

### Pitfall 3: Roll-Spanning VWAP Jumps Mid-Week or Mid-Month
**What goes wrong:** Weekly or monthly VWAP jumps by tens of points on quarterly roll dates.
**Why it happens:** Mixing raw prices from old and new contracts in one cumulative numerator.
**How to avoid:** Build completed-session roll boundary deltas and shift source prices onto the target session contract axis before cumulative sums.
**Warning signs:** Weekly/monthly VWAP levels become unreachable relative to current-session price after a roll.

### Pitfall 4: Forward-Fill Crosses Anchor Boundaries
**What goes wrong:** VWAP from the prior week or month bleeds into the first pre-trade rows of the next anchor period.
**Why it happens:** Forward-filling without grouping by the anchor ID.
**How to avoid:** Forward-fill over `weekly_anchor_id` and `monthly_anchor_id`, not globally or only by `trading_date`.
**Warning signs:** Monday 9:30 pre-trade rows already show Friday's weekly VWAP.

### Pitfall 5: `REGM-03` Scope Drift
**What goes wrong:** The plan expands into setup-detector redesign or strategy tuning work that the current Phase 8 context deferred.
**Why it happens:** The roadmap requirement is broader than the locked context.
**How to avoid:** Treat Phase 8 as delivering stable regime metadata and compatibility surfaces now; note later selectivity tuning as a dependent follow-on task.
**Warning signs:** The plan proposes changing Phase 4 signal thresholds before Phase 8 artifacts exist.

## Code Examples

Verified patterns from official docs and local repo precedent:

### Weekly and Monthly Anchor IDs
```python
# Source: https://docs.pola.rs/api/python/dev/reference/expressions/api/polars.Expr.dt.iso_year.html
# Source: https://docs.pola.rs/api/python/version/0.20/reference/expressions/api/polars.Expr.dt.week.html
# Source: https://docs.pola.rs/api/python/version/0.20/reference/expressions/api/polars.Expr.dt.month_start.html
df = df.with_columns(
    pl.struct(
        pl.col("trading_date").dt.iso_year().alias("iso_year"),
        pl.col("trading_date").dt.week().alias("iso_week"),
    ).alias("weekly_anchor_id"),
    pl.col("trading_date").dt.month_start().alias("monthly_anchor_id"),
)
```

### Cumulative VWAP Over an Anchor Group
```python
# Source: local repo pattern from src/vwap_revert/indicators/vwap.py
trade_rows = trade_rows.with_columns(
    (pl.col("adjusted_price") * pl.col("size")).alias("notional")
).with_columns(
    pl.col("notional").cum_sum().over("weekly_anchor_id").alias("weekly_cum_notional"),
    pl.col("size").cum_sum().over("weekly_anchor_id").alias("weekly_cum_volume"),
).with_columns(
    (pl.col("weekly_cum_notional") / pl.col("weekly_cum_volume")).alias("weekly_vwap")
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Daily-only RTH VWAP | Multi-timeframe VWAP reusing the same causal trade-only semantics | Repo Phase 2 established the base; Phase 8 should extend it | Keeps anchor methodology consistent across timeframes. |
| Null or reset on mixed-roll higher-timeframe windows | Deterministic roll-bridged higher-timeframe calculations on the active contract axis | Repo Phase 7 verified this on 2026-04-03 | Phase 8 should inherit the same continuity model. |
| Informal "high vol day" reasoning | Explicit session-level realized-vol metadata with binary `short_gamma` / `long_gamma` labels | Locked in Phase 8 context on 2026-04-03 | Makes regime classification auditable and joinable downstream. |

**Deprecated/outdated:**
- Using raw `year` + `week` as a weekly key: replace with ISO year + ISO week.
- Computing regime from same-day full-session volatility: replace with prior-completed-session classification.

## Open Questions

1. **Which realized-vol formula should Phase 8 standardize on?**
   - What we know: it must be session-level, causal, deterministic, and auditable.
   - What's unclear: whether to use close-to-close log returns, intraday realized variance from 1-second rows, or an RTH-range proxy.
   - Recommendation: use session-close log-return volatility over prior completed sessions first; it is the simplest causal baseline and easiest to validate in fixtures.

2. **How should `REGM-03` be represented without violating deferred scope?**
   - What we know: requirement text mentions regime-adjusted expectations, but locked deferred ideas say full selectivity tuning is not part of baseline Phase 8 context.
   - What's unclear: whether the planner should schedule detector-threshold edits now.
   - Recommendation: make Phase 8 emit regime metadata and optional threshold suggestion columns only; schedule actual detector-threshold enforcement after the Phase 8 artifacts exist.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | all Phase 8 code/tests | yes | 3.14.3 | none |
| Polars | indicator implementation | yes | 1.39.2 local | Align local env to pinned `>=1.39.3,<1.40` if version-specific behavior appears |
| PyArrow | parquet artifacts | yes | 23.0.1 | none |
| NumPy | numeric validation helpers | yes | 2.4.4 | none |
| pytest | validation architecture | yes | 8.4.2 local | Upgrade to pinned `>=9.0.2,<10` for exact repo parity |

**Missing dependencies with no fallback:**
- None.

**Missing dependencies with fallback:**
- None, but the local environment is behind the repo's pinned versions for `polars` and `pytest`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 locally, pinned to 9.0.2 in `pyproject.toml` |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/indicators/test_phase8_regime.py tests/indicators/test_phase8_regime_vwap_validation.py -q` |
| Full suite command | `python -m pytest tests -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REGM-01 | Completed-session realized vol is computed causally with explicit insufficient-history state | unit | `python -m pytest tests/indicators/test_phase8_regime.py -q` | no - Wave 0 |
| REGM-02 | Sessions are labeled `short_gamma` / `long_gamma` from deterministic prior-session thresholds | unit | `python -m pytest tests/indicators/test_phase8_regime.py -q` | no - Wave 0 |
| REGM-03 | Phase 8 outputs stable regime metadata usable by downstream setup/simulation contracts | integration | `python -m pytest tests/indicators/test_phase8_regime_vwap_validation.py -q` | no - Wave 0 |
| VWAP-04 | Weekly VWAP resets by ET trading week, stays causal, and bridges rolls | unit | `python -m pytest tests/indicators/test_phase8_regime.py -q` | no - Wave 0 |
| VWAP-05 | Monthly VWAP resets by ET calendar month, stays causal, and bridges rolls | unit | `python -m pytest tests/indicators/test_phase8_regime.py -q` | no - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/indicators/test_phase8_regime.py -q`
- **Per wave merge:** `python -m pytest tests/indicators/test_phase8_regime.py tests/indicators/test_phase8_regime_vwap_validation.py -q`
- **Phase gate:** `python -m pytest tests -q`

### Wave 0 Gaps
- [ ] `tests/indicators/test_phase8_regime.py` - core regime math, causal labeling, weekly/monthly VWAP, mixed-roll anchor coverage
- [ ] `tests/indicators/test_phase8_regime_vwap_validation.py` - artifact names, validation CSV schema, CLI command, manifest coverage
- [ ] `src/vwap_revert/indicators/regime.py` - new reusable session-summary and enrichment module
- [ ] `src/vwap_revert/cli.py` - new `build-phase8-regime-vwap` command and argument parser wiring

## Sources

### Primary (HIGH confidence)
- Local repo code:
  - `src/vwap_revert/indicators/vwap.py` - causal cumulative VWAP, null-before-anchor, forward-fill
  - `src/vwap_revert/indicators/volume_profile.py` - completed-session roll-bridging precedent
  - `src/vwap_revert/data_pipeline/sessions.py` - canonical `trading_date` semantics
  - `src/vwap_revert/indicators/setup_detection.py` - placeholder `regime_label` / `regime_reason` contract
  - `src/vwap_revert/simulation.py` - downstream regime carry-through contract
  - `src/vwap_revert/cli.py` - artifact rebuild and validation command pattern
- Official docs:
  - Polars `dt.iso_year`: https://docs.pola.rs/api/python/dev/reference/expressions/api/polars.Expr.dt.iso_year.html
  - Polars `dt.week`: https://docs.pola.rs/api/python/version/0.20/reference/expressions/api/polars.Expr.dt.week.html
  - Polars `dt.month_start`: https://docs.pola.rs/api/python/version/0.20/reference/expressions/api/polars.Expr.dt.month_start.html
  - Polars `group_by_dynamic`: https://docs.pola.rs/api/python/stable/reference/dataframe/api/polars.DataFrame.group_by_dynamic.html
  - Polars `cum_sum`: https://docs.pola.rs/py-polars/html/reference/expressions/api/polars.cum_sum.html
- Package registries:
  - Polars PyPI: https://pypi.org/project/polars/
  - PyArrow PyPI: https://pypi.org/project/pyarrow/
  - pytest PyPI: https://pypi.org/project/pytest/
  - tzdata PyPI: https://pypi.org/project/tzdata/

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` - internal domain guidance on regime proxy risk and roll-spanning VWAP pitfalls
- `.planning/research/ARCHITECTURE.md` - internal recommendation to keep indicator stages DataFrame-in/DataFrame-out

### Tertiary (LOW confidence)
- None. I did not rely on unverified community sources for Phase 8 recommendations.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - directly verified against the repo and official package/docs sources
- Architecture: HIGH - strongly constrained by existing implemented Phase 2 and Phase 7 patterns
- Pitfalls: MEDIUM - weekly/monthly VWAP pitfalls are clear, but regime threshold calibration remains inherently proxy-based

**Research date:** 2026-04-03
**Valid until:** 2026-05-03
