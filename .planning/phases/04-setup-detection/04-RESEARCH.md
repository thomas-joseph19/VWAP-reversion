# Phase 04: Setup Detection - Research

**Researched:** 2026-04-02
**Domain:** Row-aligned VWAP/structural signal composition, trading-window gating, and deterministic setup-event extraction
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
### Trading-window gating
- **D-01:** Evaluate setup eligibility only on rows whose `ts_recv_et` falls inside a configurable RTH window, defaulting to `09:30:00` through `11:30:00` America/New_York on the row's existing `trading_date`.
- **D-02:** Reuse the Phase 1 session labels and Phase 2/3 row-aligned datasets rather than rebuilding calendars or sessions inside the setup detector.
- **D-03:** Treat rows outside the configured window as definitively ineligible, but preserve explicit boolean columns showing whether the row passed the time-window filter so downstream phases can audit why a candidate was or was not emitted.

### VWAP-extension semantics
- **D-04:** Detect extension from the current row's actionable price relative to the Phase 2 `daily_vwap` and `daily_sigma`, computing a signed sigma-distance feature so later phases can distinguish above-VWAP and below-VWAP setups.
- **D-05:** Use a configurable absolute sigma range with defaults `1.7` to `3.0`, interpreted inclusively at both bounds for the initial MVP detector.
- **D-06:** If `daily_vwap` or `daily_sigma` is null or `daily_sigma` is zero, mark the row as not extended instead of attempting fallback math or synthetic normalization.

### Structural confluence and candidate emission
- **D-07:** Require at least one active structural proximity hit from Phase 3 (`structural_levels_within_threshold >= 1`) for a row to qualify as a candidate setup.
- **D-08:** Emit candidate setups on the transition into a valid combined state rather than on every qualifying second, so the Phase 4 log captures one deterministic setup event per contiguous excursion episode and avoids flooding later trade-simulation phases with duplicate entries.
- **D-09:** Assign the candidate direction from the sign of the signed sigma-distance: positive extension implies a short reversion candidate, negative extension implies a long reversion candidate.

### Output artifacts and logged context
- **D-10:** Materialize both a row-aligned enriched parquet with setup flags/features and a compact setup-log artifact containing one row per emitted candidate.
- **D-11:** Log every emitted setup with timestamp, trading date, actionable price, `daily_vwap`, `daily_sigma`, signed sigma distance, nearest structural level, nearest structural distance, structural hit count, bid/ask when available, and placeholder regime fields that remain null until Phase 8.
- **D-12:** Keep column names explicit and machine-friendly so the same Phase 4 artifacts can feed Phase 5 trade simulation and later analytics without reshaping.

### Claude's Discretion
- Exact helper boundaries for row enrichment versus setup-log extraction.
- Whether the compact setup log is emitted as parquet only or parquet plus a lightweight CSV preview, as long as it stays deterministic.
- Additional diagnostic columns that improve auditability without changing the core setup definition.

### Deferred Ideas (OUT OF SCOPE)
- Mechanical continuation-failure confirmation belongs to Phase 9, not Phase 4.
- Gamma-regime-aware thresholds belong to Phase 8 once realized-volatility classification exists.
- Multi-structural confluence scoring and advanced ranking belong to later strategy-integration work, not the MVP detector.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VWAP-03 | System detects when price is extended from VWAP within configurable deviation thresholds (default 1.7σ to 3.0σ) | Use a signed sigma-distance computed from the row's actionable price vs `daily_vwap` / `daily_sigma`, then gate with inclusive absolute bounds and null-safe handling for missing or zero sigma |
| SGNL-01 | System filters trading opportunities to the first 1-2 hours of RTH (configurable window, default 9:30-11:30 ET) | Build a dedicated time-window predicate from `ts_recv_et`, preserve it as an explicit boolean column, and never recompute sessions or calendars in Phase 4 |
| SGNL-02 | System detects combined conditions - price extended from VWAP AND at a structural level AND within the time window | Compose row-aligned boolean predicates from Phase 2 and Phase 3 outputs, then emit setup events only on `False -> True` transitions of the combined predicate |
| SGNL-03 | System logs each detected setup with full context (sigma level, which structural level, time, regime, bid/ask at signal) | Emit a deterministic event log from the already enriched frame, selecting one row per excursion episode and carrying forward explicit numeric context plus nullable regime placeholders |
</phase_requirements>

## Summary

Phase 04 should be planned as a pure composition layer, not a new indicator engine. The repo already has the upstream ingredients in row-aligned form: Phase 2 supplies causal `daily_vwap` and `daily_sigma`, Phase 3 supplies actionable-price structural proximity and nearest-level metadata, and the CLI already follows a deterministic artifact-writing pattern. The detector should therefore load the canonical cache, attach upstream enrichments, derive a small set of explicit booleans and numeric features, and then extract transition-based setup events from that frame.

The main implementation risk is determinism at episode boundaries. The planner should make transition logic, null semantics, and artifact schema explicit up front: rows outside the time window remain in the enriched artifact but are ineligible; rows with missing/zero VWAP sigma never qualify; structural confluence is a hard gate; and the setup log emits the first qualifying row in each contiguous episode only. That keeps Phase 4 aligned with the locked decisions and prevents duplicate signals from complicating Phase 5.

Testing should focus on edge behavior, not just happy-path filters: inclusive sigma bounds, exact 09:30/11:30 timestamps, DST-safe ET gating via existing `ts_recv_et`, episode reset behavior when any constituent predicate flips false, and setup-log field completeness. The existing Phase 2/3 validation tests already provide the right template for both unit and artifact-level coverage.

**Primary recommendation:** Implement Phase 04 as a new indicator-style module plus a `build-phase4-setup-detection` CLI command that derives row-level eligibility/features first and then writes a separate transition-based setup log from that same enriched frame.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `polars` | Repo target `>=1.39.3,<1.40`; current env `1.39.2`; latest PyPI release `1.39.3` (2026-03-20) | Row-aligned joins, boolean predicate composition, transition detection, parquet output | Already used in every phase and directly supports the `with_row_index`, `over`, forward-fill, join, and parquet patterns this phase needs |
| `pyarrow` | Repo target `>=23.0.1,<24`; current env `23.0.1`; latest PyPI release `23.0.1` (2026-02-16) | Arrow-backed parquet writing for downstream artifacts | Phase 1 cache and prior phases already standardize on Arrow-backed parquet outputs |
| `numpy` | Repo target `>=2.4.4,<3`; current env `2.4.4` | Optional scalar helper math only | Already in the repo stack, but Phase 04 should stay mostly in Polars expressions instead of dropping into array code |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | Repo target `>=9.0.2,<10`; current env `8.4.2`; latest PyPI release `9.0.2` (2025-12-06) | Deterministic unit and artifact/CLI tests | Use for predicate edge cases, event-transition coverage, and setup-log schema checks |
| Python `datetime` | Python 3.14.3 stdlib | Parsing configurable `HH:MM:SS` window bounds and comparing ET times | Use for explicit config parsing rather than custom string slicing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Row-aligned detector in `indicators/` | New `strategy/` scanner package now | The architecture notes point toward `strategy/scanner.py` later, but the current repo pattern and Phase 4 scope fit better as an artifact-producing indicator layer |
| Transition detection in Polars columns | Python row loop over all rows | Easier to reason about initially, but slower, less idiomatic here, and harder to keep schema-first/testable |
| Recomputing setup inputs in Phase 4 | Reuse Phase 2/3 enrichers directly | Recomputing increases drift risk and violates the locked decision to reuse existing row-aligned datasets |

**Installation:**
```bash
python -m pip install -e .[dev]
```

**Version verification:**
- `polars` latest release `1.39.3` on PyPI, published 2026-03-20.
- `pyarrow` latest release `23.0.1` on PyPI, published 2026-02-16.
- `pytest` latest release `9.0.2` on PyPI, published 2025-12-06.
- Local environment currently imports `polars 1.39.2`, `pyarrow 23.0.1`, `numpy 2.4.4`, and `pytest 8.4.2`.

## Architecture Patterns

### Recommended Project Structure
```text
src/
|-- vwap_revert/
|   |-- cli.py                             # Phase command registration
|   |-- indicators/
|   |   |-- vwap.py                        # Existing Phase 2 enrichment surface
|   |   |-- structural_levels.py           # Existing Phase 3 enrichment surface
|   |   `-- setup_detection.py             # Phase 4 row enrichment + setup extraction
|   `-- data_pipeline/
|       `-- cache.py                       # Canonical cache reload surface
tests/
`-- indicators/
    |-- test_vwap.py
    |-- test_structural_levels.py
    |-- test_vwap_validation.py
    |-- test_structural_levels_validation.py
    `-- test_setup_detection.py            # Phase 4 unit and transition tests
```

### Pattern 1: Enrich once, then extract setup events from the enriched frame
**What:** Build Phase 4 as two explicit steps: first attach setup-related columns to every row, then derive the one-row-per-setup event log by filtering transition rows from that enriched dataset.
**When to use:** Always. The event log should be a projection of the enriched artifact, not a separately computed pipeline.
**Example:**
```python
enriched = source.with_columns(
    time_window_passes=...,
    setup_sigma_signed=...,
    vwap_extension_passes=...,
    setup_combined_passes=...,
)

setup_log = enriched.filter(
    pl.col("setup_combined_passes")
    & ~pl.col("setup_combined_passes").shift(1).fill_null(False).over("trading_date")
)
```
Source: local Phase 2/3 row-aligned artifact pattern plus Polars window-expression docs

### Pattern 2: Reuse upstream actionable-price semantics
**What:** Use the row's best actionable price for both structural and VWAP-extension logic rather than mixing raw trade price for some rows and midpoint logic for others.
**When to use:** For all signed sigma-distance and setup logging fields.
**Example:**
```python
actionable_price = (
    pl.when(pl.col("side").is_in(["A", "B"]))
    .then(pl.col("price"))
    .when(pl.all_horizontal(pl.col("bid_px_00").is_not_null(), pl.col("ask_px_00").is_not_null()))
    .then((pl.col("bid_px_00") + pl.col("ask_px_00")) / 2.0)
    .when(pl.col("bid_px_00").is_not_null())
    .then(pl.col("bid_px_00"))
    .when(pl.col("ask_px_00").is_not_null())
    .then(pl.col("ask_px_00"))
    .otherwise(None)
)
```
Source: [src/vwap_revert/indicators/structural_levels.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/structural_levels.py)

### Pattern 3: Preserve explicit audit columns for each constituent gate
**What:** Keep separate columns for time-window pass, sigma-distance value, extension pass, structural pass, combined pass, and setup direction, even if only the combined predicate drives event emission.
**When to use:** Always. Downstream analytics and debugging need to know why a row did or did not produce a setup.
**Example:**
```python
enriched = enriched.with_columns(
    (pl.col("ts_recv_et").dt.time().is_between(window_start, window_end, closed="both")).alias("time_window_passes"),
    (((pl.col("actionable_price") - pl.col("daily_vwap")) / pl.col("daily_sigma"))).alias("setup_sigma_signed"),
    (pl.col("structural_levels_within_threshold") >= 1).alias("structural_confluence_passes"),
)
```
Source: Phase 04 locked decisions D-01 through D-07 and Polars expression docs

### Pattern 4: Keep setup-log schemas forward-compatible
**What:** Include nullable regime placeholders and direct numeric context fields now, instead of forcing later phases to backfill or reshape the log.
**When to use:** In the compact one-row-per-setup artifact.
**Example:**
```python
setup_log = transition_rows.select(
    "trading_date",
    "ts_recv_et",
    "actionable_price",
    "daily_vwap",
    "daily_sigma",
    "setup_sigma_signed",
    "setup_direction",
    "nearest_structural_level",
    "nearest_structural_distance",
    "structural_levels_within_threshold",
    "bid_px_00",
    "ask_px_00",
    pl.lit(None, dtype=pl.Utf8).alias("regime_label"),
)
```
Source: Phase 04 locked decisions D-10 through D-12

### Anti-Patterns to Avoid
- **Rebuilding session logic in Phase 4:** Use `ts_recv_et`, `trading_date`, and prior-phase enrichers already present in the canonical row stream.
- **Dropping non-qualifying rows from the enriched artifact:** The setup detector needs a reusable row-aligned output, not only a sparse event log.
- **Event logging on every qualifying second:** This violates D-08 and will pollute Phase 5 with duplicate entries.
- **Using raw `price` blindly for all rows:** Quote-only rows need the same actionable-price semantics already used by structural proximity.
- **Hiding null/zero sigma rows behind synthetic defaults:** Those rows must fail cleanly and visibly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Session/timezone logic | New calendar or DST calculator | Existing `ts_recv_et`, `trading_date`, and Phase 1 session labels | The time semantics are already locked and tested upstream |
| Upstream indicator recomputation | New VWAP or structural math in Phase 4 | `attach_daily_vwap_bands()` and `attach_prior_day_structural_levels()` patterns / artifacts | Prevents drift and keeps Phase 4 focused on composition |
| Artifact layout | Ad hoc CSV-only detector output | Same parquet + validation-manifest conventions used in Phases 2 and 3 | Downstream phases already depend on deterministic file artifacts |
| Transition state machine over full dataset | Large custom Python iterator | Polars boolean masks plus per-session `shift()` | The state transition is simple and naturally columnar here |

**Key insight:** Phase 04 is mostly schema and state-boundary work. The planner should spend effort on row semantics, explicit gating columns, and deterministic event extraction, not on inventing new infrastructure.

## Common Pitfalls

### Pitfall 1: Time-window gating on the wrong timezone column
**What goes wrong:** Signals shift by one hour around DST boundaries or compare against UTC instead of ET.
**Why it happens:** The detector uses `ts_recv` directly instead of the already-normalized `ts_recv_et`.
**How to avoid:** Gate exclusively on `ts_recv_et` and parse configured bounds into `datetime.time` values.
**Warning signs:** Rows at `14:30 UTC` behave differently before versus after March/November DST transitions.

### Pitfall 2: Event transitions leaking across session boundaries
**What goes wrong:** The first qualifying row of a new trading day is suppressed because the previous day's final row was also `True`.
**Why it happens:** The prior-state comparison uses a global `shift(1)` without resetting by `trading_date`.
**How to avoid:** Compute the previous combined-state value with `over("trading_date")`.
**Warning signs:** A fixture with two consecutive qualifying sessions emits only one setup total.

### Pitfall 3: Extension logic dividing by null or zero sigma
**What goes wrong:** Rows emit infinities, NaNs, or false positives early in the session.
**Why it happens:** The detector does not explicitly guard `daily_sigma == 0` or null VWAP/sigma rows.
**How to avoid:** Set signed sigma-distance to null when inputs are missing or zero and derive `vwap_extension_passes=False` from that state.
**Warning signs:** The first trade row of a session can qualify as extended before variance exists.

### Pitfall 4: Structural and VWAP predicates using different price semantics
**What goes wrong:** A row appears structurally near a level but not extended, or vice versa, for reasons unrelated to strategy intent.
**Why it happens:** Structural logic uses actionable price while VWAP extension uses raw `price`.
**How to avoid:** Use one explicit actionable-price column for all Phase 4 predicates and logging.
**Warning signs:** Quote-only rows have null or misleading sigma-distance while still showing structural confluence.

### Pitfall 5: Setup log missing enough context for Phase 5
**What goes wrong:** Trade simulation has to rejoin row-level artifacts just to recover direction, sigma, or nearest structural metadata.
**Why it happens:** The event log is treated as a minimal signal list rather than a reusable handoff artifact.
**How to avoid:** Include the full context columns named in D-11 plus stable identifiers like `trading_date` and setup timestamp.
**Warning signs:** Planner tasks for Phase 5 require new joins before entry logic can start.

## Code Examples

Verified patterns from local code and official docs:

### Row-stable join pattern for reusable enrichment
```python
base = df.with_row_index("__row")
enriched = base.join(indicator_rows, on=["trading_date", "ts_recv"], how="left").sort("__row").drop("__row")
```
Source: [src/vwap_revert/indicators/vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/vwap.py)

### Per-session state comparison with window expressions
```python
previous_state = pl.col("setup_combined_passes").shift(1).fill_null(False).over("trading_date")
```
Source: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html

### Datetime-to-time extraction for window gating
```python
pl.col("ts_recv_et").dt.time()
```
Source: https://docs.pola.rs/api/python/version/0.19/reference/expressions/api/polars.Expr.dt.time.html

### Partitioned parquet cache reload for upstream inputs
```python
scan_canonical_cache(cache_root).collect()
```
Source: [src/vwap_revert/data_pipeline/cache.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/data_pipeline/cache.py)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Session-only indicator outputs with downstream recomputation | Row-aligned reusable artifacts per phase | Established by Phases 2-3 on 2026-04-02 | Phase 4 should stay compositional and avoid recomputing upstream state |
| Logging every qualifying bar as a setup | Transition-based single-event emission per excursion episode | Locked in Phase 04 context on 2026-04-02 | Prevents duplicate Phase 5 trades and keeps the signal log deterministic |
| Regime-aware setup thresholds in baseline detector | Fixed 1.7-3.0 sigma bounds plus nullable regime placeholders | Locked in Phase 04 context on 2026-04-02 | Keeps MVP focused while preserving schema compatibility for Phase 8 |

**Deprecated/outdated:**
- Treating Phase 4 as trade-entry logic: continuation-failure confirmation and execution remain out of scope until later phases.
- Rebuilding calendars or sessions in each phase: Phase 1 already established the canonical timestamps and labels.

## Open Questions

1. **Should Phase 4 accept prebuilt Phase 2/3 artifacts as CLI inputs, or always recompute enrichments from the canonical cache?**
   - What we know: Locked decision D-02 says reuse Phase 2/3 row-aligned datasets rather than rebuilding session logic.
   - What's unclear: Whether the planner wants strict artifact chaining or in-process reuse of the helper functions against the canonical cache.
   - Recommendation: Plan for canonical-cache input plus in-process reuse of the Phase 2/3 helper surfaces first; add explicit artifact-input options only if rebuild time becomes material.

2. **Should the compact setup log also emit a CSV preview?**
   - What we know: The user allowed parquet only or parquet plus lightweight CSV as long as it is deterministic.
   - What's unclear: Whether manual inspection of setup events will be frequent enough to justify the extra artifact.
   - Recommendation: Keep parquet as the source of truth and make CSV preview optional only if a validation plan explicitly needs it.

3. **What exact column names should the planner freeze for Phase 5 compatibility?**
   - What we know: D-12 requires explicit machine-friendly names and D-11 specifies minimum context.
   - What's unclear: Whether later phases want names like `setup_direction` / `setup_sigma_signed` or `candidate_direction` / `signed_sigma_distance`.
   - Recommendation: Freeze names during planning and use them consistently across the enriched parquet and compact setup log to avoid downstream rename churn.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Package runtime and CLI | Yes | 3.14.3 | - |
| `polars` | Row-level setup enrichment and event extraction | Yes | 1.39.2 | Works now; align to repo target `>=1.39.3,<1.40` if strict version parity matters |
| `pyarrow` | Parquet artifact writing | Yes | 23.0.1 | - |
| `numpy` | Optional scalar helper math | Yes | 2.4.4 | Pure Python if needed |
| `python -m pytest` | Automated validation | Yes | 8.4.2 | - |
| `pytest` on PATH | Direct CLI invocation | No | - | Use `python -m pytest` |

**Missing dependencies with no fallback:**
- None identified for Phase 04 planning.

**Missing dependencies with fallback:**
- `pytest` CLI is not on PATH; use `python -m pytest`.
- Local `polars` and `pytest` versions lag the repo target pins, so avoid depending on APIs newer than `polars 1.39.2` unless the environment is synced first.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 8.4.2` installed, repo declares `pytest>=9.0.2,<10` |
| Config file | `pyproject.toml` |
| Quick run command | `python -m pytest tests/indicators/test_setup_detection.py -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VWAP-03 | Signed sigma-distance and inclusive extension bounds behave correctly, including null/zero sigma handling | unit | `python -m pytest tests/indicators/test_setup_detection.py -q` | No - Wave 0 |
| SGNL-01 | Time-window gating uses ET timestamps and inclusive 09:30-11:30 defaults | unit | `python -m pytest tests/indicators/test_setup_detection.py -q` | No - Wave 0 |
| SGNL-02 | Combined predicate emits one setup per contiguous qualifying episode and resets per `trading_date` | unit | `python -m pytest tests/indicators/test_setup_detection.py -q` | No - Wave 0 |
| SGNL-03 | CLI writes enriched parquet plus compact setup-log artifact with required fields | integration | `python -m pytest tests/indicators/test_setup_detection_validation.py -q` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/indicators/test_setup_detection.py -q`
- **Per wave merge:** `python -m pytest tests/indicators -q`
- **Phase gate:** `python -m pytest -q`

### Wave 0 Gaps
- [ ] `tests/indicators/test_setup_detection.py` - deterministic unit coverage for time-window boundaries, inclusive sigma thresholds, null/zero sigma handling, direction assignment, and episode transitions
- [ ] `tests/indicators/test_setup_detection_validation.py` - artifact writer and CLI coverage mirroring the Phase 2 and Phase 3 validation tests
- [ ] A shared Phase 4 fixture frame that includes trade rows, quote-only rows, bid/ask columns, and at least two sessions to validate per-day transition resets

## Sources

### Primary (HIGH confidence)
- [Local phase context] [04-CONTEXT.md](/c:/Users/pranav/Desktop/trading/vwap%20revert/.planning/phases/04-setup-detection/04-CONTEXT.md) - locked Phase 4 decisions, scope, and canonical references
- [Local requirements] [REQUIREMENTS.md](/c:/Users/pranav/Desktop/trading/vwap%20revert/.planning/REQUIREMENTS.md) - `VWAP-03`, `SGNL-01`, `SGNL-02`, `SGNL-03`
- [Local roadmap] [ROADMAP.md](/c:/Users/pranav/Desktop/trading/vwap%20revert/.planning/ROADMAP.md) - Phase 4 goal and success criteria
- [Local CLI pattern] [cli.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/cli.py) - deterministic phase command structure
- [Local Phase 2 indicator] [vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/vwap.py) - row-aligned VWAP enrichment pattern
- [Local Phase 3 indicator] [structural_levels.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/src/vwap_revert/indicators/structural_levels.py) - actionable-price and structural proximity pattern
- [Local tests] [test_vwap.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/tests/indicators/test_vwap.py), [test_structural_levels.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/tests/indicators/test_structural_levels.py), [test_vwap_validation.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/tests/indicators/test_vwap_validation.py), [test_structural_levels_validation.py](/c:/Users/pranav/Desktop/trading/vwap%20revert/tests/indicators/test_structural_levels_validation.py) - established test and artifact-validation style
- https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.Expr.over.html - verified window-expression behavior used for per-session transition detection
- https://docs.pola.rs/api/python/version/0.19/reference/expressions/api/polars.Expr.dt.time.html - verified datetime-to-time extraction API for time-window gating
- https://docs.python.org/3.14/library/datetime.html - verified `datetime.time` parsing/semantics for configurable window bounds
- https://pypi.org/project/polars/0.14.29/ - release history showing `1.39.3` published 2026-03-20
- https://pypi.org/project/pyarrow/ - release history showing `23.0.1` published 2026-02-16
- https://pypi.org/project/pytest/ - release history showing `9.0.2` published 2025-12-06

### Secondary (MEDIUM confidence)
- [Local architecture note] [ARCHITECTURE.md](/c:/Users/pranav/Desktop/trading/vwap%20revert/.planning/research/ARCHITECTURE.md) - high-level recommendation that setup scanning remains a vectorized filter stage before later sequential trade simulation

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - the stack is already pinned in `pyproject.toml`, present locally, and mostly verified against current package metadata
- Architecture: HIGH - Phase 2 and Phase 3 provide a direct implementation template for Phase 4
- Pitfalls: HIGH - the major risks are explicit in the locked decisions and visible from current row-aligned code patterns

**Research date:** 2026-04-02
**Valid until:** 2026-05-02
